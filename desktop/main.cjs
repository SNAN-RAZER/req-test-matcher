const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const http = require("http");

const ROOT = path.resolve(__dirname, "..");
const HOST = "127.0.0.1";
const PORT = Number(process.env.APP_PORT || 8080);
const URL = `http://${HOST}:${PORT}/`;

let api = null;
let startedApi = false;

function pythonBin() {
  const unix = path.join(ROOT, ".venv", "bin", "python");
  const win = path.join(ROOT, ".venv", "Scripts", "python.exe");
  if (fs.existsSync(unix)) return unix;
  if (fs.existsSync(win)) return win;
  return null;
}

function health() {
  return new Promise((resolve) => {
    const req = http.get(`http://${HOST}:${PORT}/api/health`, (res) => {
      resolve(res.statusCode >= 200 && res.statusCode < 500);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(800, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForApi(ms = 60000) {
  const start = Date.now();
  while (Date.now() - start < ms) {
    if (await health()) return true;
    await new Promise((r) => setTimeout(r, 400));
  }
  return false;
}

function startApi() {
  const py = pythonBin();
  if (!py) {
    throw new Error("No .venv Python. Run: python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt");
  }
  const dist = path.join(ROOT, "web", "dist", "index.html");
  if (!fs.existsSync(dist)) {
    throw new Error("React UI is not built. Run: cd web && npm install && npm run build");
  }
  api = spawn(py, ["-m", "app.main"], {
    cwd: ROOT,
    env: { ...process.env, APP_HOST: HOST, APP_PORT: String(PORT) },
    stdio: "inherit",
  });
  startedApi = true;
  api.on("exit", (code) => {
    if (code && code !== 0) {
      console.error("API exited", code);
    }
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 840,
    minWidth: 960,
    minHeight: 640,
    title: "Req–Test Matcher",
    backgroundColor: "#12110f",
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  win.loadURL(URL);
}

async function boot() {
  if (!(await health())) {
    startApi();
    const ok = await waitForApi();
    if (!ok) {
      dialog.showErrorBox(
        "API did not start",
        "Could not reach http://127.0.0.1:8080. Check Ollama and that the venv is installed."
      );
      app.quit();
      return;
    }
  }
  createWindow();
}

app.whenReady().then(boot).catch((err) => {
  dialog.showErrorBox("Failed to start", String(err && err.message ? err.message : err));
  app.quit();
});

app.on("window-all-closed", () => {
  if (startedApi && api && !api.killed) api.kill("SIGTERM");
  app.quit();
});
