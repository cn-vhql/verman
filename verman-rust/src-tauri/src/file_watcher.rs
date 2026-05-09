use std::path::PathBuf;
use std::sync::mpsc;
use std::time::{Duration, Instant};

use notify::{Config, Event, RecommendedWatcher, RecursiveMode, Watcher};
use tauri::Emitter;

pub struct FileWatcher {
    _watcher: RecommendedWatcher,
    _stop_tx: mpsc::Sender<()>,
}

impl FileWatcher {
    pub fn start(path: PathBuf, app_handle: tauri::AppHandle) -> Result<Self, String> {
        let (event_tx, event_rx) = mpsc::channel::<Result<Event, notify::Error>>();

        let mut watcher = RecommendedWatcher::new(
            move |event: Result<Event, notify::Error>| {
                let _ = event_tx.send(event);
            },
            Config::default(),
        )
        .map_err(|e| format!("Failed to create file watcher: {}", e))?;

        watcher
            .watch(&path, RecursiveMode::Recursive)
            .map_err(|e| format!("Failed to start watching: {}", e))?;

        let (stop_tx, stop_rx) = mpsc::channel::<()>();
        let debounce = Duration::from_millis(300);
        let check_interval = Duration::from_millis(100);

        std::thread::spawn(move || {
            let mut last_event: Option<Instant> = None;

            loop {
                match stop_rx.recv_timeout(check_interval) {
                    Ok(()) | Err(mpsc::RecvTimeoutError::Disconnected) => break,
                    Err(mpsc::RecvTimeoutError::Timeout) => {}
                }

                loop {
                    match event_rx.try_recv() {
                        Ok(Ok(event)) => {
                            let is_verman = event
                                .paths
                                .iter()
                                .any(|p| p.to_string_lossy().contains(".verman"));
                            if !is_verman {
                                last_event = Some(Instant::now());
                            }
                        }
                        Ok(Err(_)) => {}
                        Err(mpsc::TryRecvError::Empty) => break,
                        Err(mpsc::TryRecvError::Disconnected) => return,
                    }
                }

                if let Some(time) = last_event {
                    if time.elapsed() >= debounce {
                        let _ = app_handle.emit("verman:files-changed", ());
                        last_event = None;
                    }
                }
            }
        });

        Ok(Self {
            _watcher: watcher,
            _stop_tx: stop_tx,
        })
    }
}
