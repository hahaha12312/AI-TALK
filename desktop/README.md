# 🖥️ AI-TALK 桌面端（Tauri）

用 [Tauri](https://tauri.app) 把 `frontend/` 打包为 Windows / macOS / Linux 桌面应用。
体积小、内存占用低（使用系统 WebView）。

## 依赖

- [Node.js](https://nodejs.org) ≥ 18
- [Rust](https://www.rust-lang.org/tools/install)（`rustup`）
- 各平台的系统依赖：见 https://tauri.app/start/prerequisites/

## 开发运行

```bash
cd desktop
npm install
npm run dev      # 打开桌面窗口，加载 ../frontend
```

> 后端需另外启动（默认 `http://localhost:8000`）：
> ```bash
> cd ../backend && uvicorn main:app --reload
> ```

## 打包安装包

```bash
cd desktop
npm run build
```

产物位于 `desktop/src-tauri/target/release/bundle/`：
- Windows：`.msi` / `.exe`(NSIS)
- macOS：`.dmg`
- Linux：`.AppImage` / `.deb`

## 图标

首次打包前需生成图标（放到 `src-tauri/icons/`）：

```bash
npx @tauri-apps/cli icon path/to/logo.png
```

## 让后端随桌面端一起启动（可选）

1. 用 PyInstaller 把后端打成单可执行文件：
   ```bash
   cd ../backend
   pip install pyinstaller
   pyinstaller --onefile --name aitalk-backend main.py
   ```
2. 把可执行文件放入 `src-tauri/binaries/`，在 `tauri.conf.json` 的
   `bundle.externalBin` 中登记为 sidecar。
3. 在 `src/main.rs` 里用 `tauri-plugin-shell` 的 sidecar 能力在应用启动时拉起后端进程。

> 注意：`tauri-plugin-shell` 请使用 ≥ 2.2.1（修复 open 端点范围校验漏洞）。

## 指向自定义后端地址

前端通过 `window.API_BASE` 覆盖默认地址。可在打包前于 `frontend/index.html`
的 `app.js` 引用前注入：

```html
<script>window.API_BASE = "http://127.0.0.1:8000";</script>
```
