const { app, BrowserWindow, dialog, shell } = require("electron");
const { spawn } = require("node:child_process");
const http = require("node:http");
const net = require("node:net");
const path = require("node:path");
const fs = require("node:fs");

let port = 5055;
const serverUrl = () => `http://127.0.0.1:${port}`;
let backendProcess = null;
let mainWindow = null;
let isQuitting = false;

function projectRoot() {
  return path.resolve(__dirname, "..");
}

function backendDir() {
  return path.join(projectRoot(), "backend");
}

function findPython() {
  const candidates = [
    process.env.PLATFORM_PYTHON,
    "D:\\Anaconda\\python.exe",
    "python",
    "py",
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (candidate === "python" || candidate === "py" || fs.existsSync(candidate)) return candidate;
  }
  return null;
}

function backendCommand() {
  if (app.isPackaged) {
    const executable = path.join(process.resourcesPath, "backend", "course-platform-backend.exe");
    return { executable, args: [], cwd: path.dirname(executable) };
  }

  const python = findPython();
  if (!python) throw new Error("未找到 Python。请安装依赖或设置 PLATFORM_PYTHON 环境变量。");
  const args = python === "py"
    ? ["-3", path.join(backendDir(), "app.py")]
    : [path.join(backendDir(), "app.py")];
  return { executable: python, args, cwd: backendDir() };
}

function findAvailablePort(preferred = 5055) {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", () => {
      const fallback = net.createServer();
      fallback.unref();
      fallback.on("error", reject);
      fallback.listen(0, "127.0.0.1", () => {
        const selected = fallback.address().port;
        fallback.close(() => resolve(selected));
      });
    });
    server.listen(preferred, "127.0.0.1", () => server.close(() => resolve(preferred)));
  });
}

function startBackend() {
  const command = backendCommand();
  if (!fs.existsSync(command.executable) && !["python", "py"].includes(command.executable)) {
    throw new Error(`后端程序不存在：${command.executable}`);
  }

  const dataDirectory = app.isPackaged
    ? path.join(app.getPath("userData"), "platform-data")
    : path.join(backendDir(), "data");
  fs.mkdirSync(dataDirectory, { recursive: true });

  backendProcess = spawn(command.executable, command.args, {
    cwd: command.cwd,
    windowsHide: true,
    env: {
      ...process.env,
      PORT: String(port),
      PLATFORM_DATA_DIR: dataDirectory,
      PLATFORM_DESKTOP: "1",
      PYTHONUNBUFFERED: "1",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });

  backendProcess.stdout.on("data", (chunk) => console.log(`[backend] ${chunk.toString().trim()}`));
  backendProcess.stderr.on("data", (chunk) => console.error(`[backend] ${chunk.toString().trim()}`));
  backendProcess.on("exit", (code) => {
    console.log(`[backend] exited with code ${code}`);
    backendProcess = null;
    if (!isQuitting && mainWindow && !mainWindow.isDestroyed()) {
      dialog.showErrorBox("后端服务已停止", "桌面应用的本地服务意外退出，请重新启动应用。");
      app.quit();
    }
  });
}

function waitForBackend(timeoutMs = 30000) {
  const startedAt = Date.now();
  return new Promise((resolve, reject) => {
    const probe = () => {
      const request = http.get(`${serverUrl()}/api/health`, { timeout: 1200 }, (response) => {
        response.resume();
        if (response.statusCode === 200) return resolve();
        schedule();
      });
      request.on("timeout", () => request.destroy());
      request.on("error", schedule);
    };
    const schedule = () => {
      if (Date.now() - startedAt > timeoutMs) return reject(new Error("后端服务启动超时"));
      setTimeout(probe, 250);
    };
    probe();
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1420,
    height: 920,
    minWidth: 1080,
    minHeight: 680,
    show: false,
    backgroundColor: "#f4f6f9",
    title: "高校课程项目协作与评审平台",
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http://") || url.startsWith("https://")) shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.once("ready-to-show", () => mainWindow.show());
  mainWindow.on("closed", () => { mainWindow = null; });
  return mainWindow;
}

function stopBackend() {
  if (!backendProcess || backendProcess.killed) return;
  const pid = backendProcess.pid;
  if (process.platform === "win32") {
    spawn("taskkill", ["/pid", String(pid), "/t", "/f"], { windowsHide: true });
  } else {
    backendProcess.kill("SIGTERM");
  }
  backendProcess = null;
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) app.quit();

app.on("second-instance", () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

app.whenReady().then(async () => {
  const window = createWindow();
  try {
    port = await findAvailablePort();
    startBackend();
    await waitForBackend();
    await window.loadURL(serverUrl());
  } catch (error) {
    dialog.showErrorBox("桌面应用启动失败", error.message);
    app.quit();
  }
});

app.on("before-quit", () => {
  isQuitting = true;
  stopBackend();
});

app.on("window-all-closed", () => app.quit());

