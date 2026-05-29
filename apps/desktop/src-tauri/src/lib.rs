use std::{
    path::PathBuf,
    sync::{Arc, Mutex},
};
use tauri::{Emitter, Manager};
use tauri_plugin_shell::{process::CommandChild, ShellExt};

#[tauri::command]
fn worker_status() -> serde_json::Value {
    serde_json::json!({
        "status": "idle",
        "paired": false
    })
}

#[tauri::command]
fn desktop_paths() -> serde_json::Value {
    let home_dir = if cfg!(windows) {
        std::env::var("USERPROFILE").ok()
    } else {
        std::env::var("HOME").ok()
    };
    let output_dir = home_dir.map(|home| {
        let mut path = PathBuf::from(home);
        path.push("POVerlay");
        path.push("Jobs");
        path.to_string_lossy().to_string()
    });

    serde_json::json!({
        "output_dir": output_dir,
    })
}

fn spawn_worker<R: tauri::Runtime>(app: &tauri::App<R>) -> Result<CommandChild, String> {
    let (_events, child) = app
        .shell()
        .sidecar("poverlay-worker")
        .map_err(|error| format!("Could not resolve local worker sidecar: {error}"))?
        .args(["serve", "--host", "127.0.0.1", "--port", "47981"])
        .spawn()
        .map_err(|error| format!("Could not start local worker: {error}"))?;
    Ok(child)
}

pub fn run() {
    let worker_process = Arc::new(Mutex::new(None));
    let setup_worker_process = Arc::clone(&worker_process);
    let close_worker_process = Arc::clone(&worker_process);

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(move |app| {
            match spawn_worker(app) {
                Ok(child) => {
                    if let Ok(mut process) = setup_worker_process.lock() {
                        *process = Some(child);
                    }
                    let _ = app.emit("worker-started", "127.0.0.1:47981");
                }
                Err(error) => {
                    let _ = app.emit("worker-error", error);
                }
            }
            Ok(())
        })
        .plugin(tauri_plugin_single_instance::init(|app, argv, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_focus();
            }
            if let Some(url) = argv.iter().find(|arg| arg.starts_with("poverlay://")) {
                let _ = app.emit("deep-link", url);
            }
        }))
        .plugin(tauri_plugin_deep_link::init())
        .invoke_handler(tauri::generate_handler![worker_status, desktop_paths])
        .on_window_event(move |_window, event| {
            if matches!(event, tauri::WindowEvent::CloseRequested { .. }) {
                if let Ok(mut process) = close_worker_process.lock() {
                    if let Some(child) = process.take() {
                        let _ = child.kill();
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running POVerlay Desktop");
}
