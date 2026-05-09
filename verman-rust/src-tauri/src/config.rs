use serde::{Deserialize, Serialize};
use std::path::PathBuf;

const DEFAULT_IGNORE_PATTERNS: &[&str] = &[
    "*.log", "*.tmp", "*.temp", "__pycache__/", "*.pyc", ".git/", ".svn/", ".hg/",
    ".DS_Store", "Thumbs.db", ".verman/", ".verman_backup/", ".verman_temp/",
    ".verman.db.bak.*",
];

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    #[serde(default)]
    pub recent_projects: Vec<String>,
    #[serde(default)]
    pub window_geometry: String,
    #[serde(default)]
    pub ignore_patterns: Vec<String>,
    #[serde(default = "default_auto_backup")]
    pub auto_backup: bool,
}

fn default_auto_backup() -> bool {
    true
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            recent_projects: Vec::new(),
            window_geometry: String::new(),
            ignore_patterns: DEFAULT_IGNORE_PATTERNS
                .iter()
                .map(|s| s.to_string())
                .collect(),
            auto_backup: true,
        }
    }
}

pub struct ConfigManager {
    config_file: PathBuf,
    config: AppConfig,
}

#[allow(dead_code)]
impl ConfigManager {
    pub fn new() -> Self {
        let config_dir = dirs::home_dir()
            .unwrap_or_else(|| PathBuf::from("."));
        let config_file = config_dir.join(".verman_config.json");
        let config = Self::load_config(&config_file);
        Self { config_file, config }
    }

    fn load_config(path: &PathBuf) -> AppConfig {
        match std::fs::read_to_string(path) {
            Ok(content) => {
                match serde_json::from_str::<AppConfig>(&content) {
                    Ok(config) => config,
                    Err(e) => {
                        tracing::warn!(error = %e, "Failed to parse config, using defaults");
                        AppConfig::default()
                    }
                }
            }
            Err(e) => {
                tracing::debug!(error = %e, "No config file found, using defaults");
                AppConfig::default()
            }
        }
    }

    fn save(&self) {
        match serde_json::to_string_pretty(&self.config) {
            Ok(content) => {
                if let Err(e) = std::fs::write(&self.config_file, content) {
                    tracing::error!(error = %e, "Failed to save config");
                }
            }
            Err(e) => {
                tracing::error!(error = %e, "Failed to serialize config");
            }
        }
    }

    pub fn get_config(&self) -> &AppConfig {
        &self.config
    }

    pub fn add_recent_project(&mut self, project_path: &str) {
        self.config.recent_projects.retain(|p| p != project_path);
        self.config.recent_projects.insert(0, project_path.to_string());
        if self.config.recent_projects.len() > 10 {
            self.config.recent_projects.truncate(10);
        }
        self.save();
    }

    pub fn get_recent_projects(&self) -> &[String] {
        &self.config.recent_projects
    }

    pub fn get_ignore_patterns(&self) -> Vec<String> {
        self.config.ignore_patterns.clone()
    }

    pub fn set_ignore_patterns(&mut self, patterns: Vec<String>) {
        self.config.ignore_patterns = patterns;
        self.save();
    }

    pub fn set_window_geometry(&mut self, geometry: &str) {
        self.config.window_geometry = geometry.to_string();
        self.save();
    }

    pub fn get_window_geometry(&self) -> &str {
        &self.config.window_geometry
    }

    pub fn is_auto_backup_enabled(&self) -> bool {
        self.config.auto_backup
    }

    pub fn set_auto_backup(&mut self, enabled: bool) {
        self.config.auto_backup = enabled;
        self.save();
    }

    pub fn reset_to_defaults(&mut self) {
        self.config = AppConfig::default();
        self.save();
    }
}
