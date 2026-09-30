// AI-TALK 桌面端入口。
// 默认加载 ../frontend 静态页面；后端（FastAPI）需单独运行在 http://localhost:8000。
// 如需随桌面端自动启动后端，可将打包好的后端可执行文件作为 sidecar，
// 在此用 tauri-plugin-shell 启动（见 desktop/README.md）。

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .run(tauri::generate_context!())
        .expect("error while running AI-TALK");
}
