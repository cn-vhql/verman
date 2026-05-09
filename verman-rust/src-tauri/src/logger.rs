use std::path::PathBuf;
use std::sync::Mutex;

use crate::models::LogEntry;

const MAX_LOGS: usize = 500;

pub struct OperationLogger {
    log_file: PathBuf,
    logs: Mutex<Vec<LogEntry>>,
}

impl OperationLogger {
    pub fn new() -> Self {
        let log_dir = dirs::home_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join(".verman");
        std::fs::create_dir_all(&log_dir).ok();
        let log_file = log_dir.join("operation_logs.json");
        let logs = Self::load_logs(&log_file);
        Self {
            log_file,
            logs: Mutex::new(logs),
        }
    }

    fn load_logs(path: &PathBuf) -> Vec<LogEntry> {
        match std::fs::read_to_string(path) {
            Ok(content) => serde_json::from_str(&content).unwrap_or_default(),
            Err(_) => Vec::new(),
        }
    }

    fn save(&self) {
        if let Ok(mut logs) = self.logs.lock() {
            if logs.len() > MAX_LOGS {
                let excess = logs.len() - MAX_LOGS;
                logs.drain(0..excess);
            }
            if let Ok(content) = serde_json::to_string_pretty(&*logs) {
                std::fs::write(&self.log_file, content).ok();
            }
        }
    }

    pub fn log_operation(
        &self,
        action: &str,
        details: &str,
        project_path: &str,
        level: &str,
    ) {
        let entry = LogEntry {
            timestamp: chrono::Local::now()
                .format("%Y-%m-%d %H:%M:%S")
                .to_string(),
            level: level.to_uppercase(),
            action: action.to_string(),
            details: details.to_string(),
            project_path: project_path.to_string(),
        };
        if let Ok(mut logs) = self.logs.lock() {
            logs.push(entry);
        }
        self.save();
    }

    pub fn get_logs(&self) -> Vec<LogEntry> {
        self.logs.lock().map(|logs| logs.clone()).unwrap_or_default()
    }

    pub fn clear_logs(&self) {
        if let Ok(mut logs) = self.logs.lock() {
            logs.clear();
        }
        self.save();
    }
}

pub fn setup_tracing() {
    let log_dir = dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".verman")
        .join("logs");
    std::fs::create_dir_all(&log_dir).ok();

    let _ = tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info".into()),
        )
        .with_target(true)
        .with_thread_ids(false)
        .with_file(true)
        .with_line_number(true)
        .try_init();
}
