const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow;
let pythonProcess = null;

const fs = require('fs');

function checkBackendReady(callback) {
  const req = http.get('http://127.0.0.1:8765/api/status', (res) => {
    if (res.statusCode === 200) {
      callback(true);
    } else {
      callback(false);
    }
  });
  req.on('error', () => callback(false));
  req.setTimeout(1000, () => {
    req.destroy();
    callback(false);
  });
}

function startBackend() {
  const backendExe = path.join(__dirname, 'backend', 'modem_bridge.exe');
  const backendScript = path.join(__dirname, 'backend', 'modem_bridge.py');
  const logFile = path.join(__dirname, 'backend', 'backend.log');
  let logStream;
  try {
    logStream = fs.createWriteStream(logFile, { flags: 'a' });
  } catch (e) {
    console.error('Cannot create backend log stream:', e);
  }

  if (fs.existsSync(backendExe)) {
    console.log('Spawning standalone backend binary:', backendExe);
    pythonProcess = spawn(backendExe, [], {
      cwd: path.join(__dirname, 'backend'),
      windowsHide: true
    });
  } else {
    const pythonExe = fs.existsSync('C:\\Python314\\python.exe') ? 'C:\\Python314\\python.exe' : 'python';
    console.log('Spawning backend script via python:', pythonExe);
    pythonProcess = spawn(pythonExe, ['-u', backendScript], {
      cwd: path.join(__dirname, 'backend'),
      windowsHide: true
    });
  }

  if (pythonProcess.stdout && logStream) {
    pythonProcess.stdout.pipe(logStream);
  }
  if (pythonProcess.stderr && logStream) {
    pythonProcess.stderr.pipe(logStream);
  }

  pythonProcess.on('error', (err) => {
    console.error('Failed to start backend process:', err);
    try {
      fs.appendFileSync(logFile, `[MAIN ERROR] Failed to start backend: ${err.message}\n`);
    } catch (e) {}
  });

  pythonProcess.on('exit', (code, signal) => {
    try {
      fs.appendFileSync(logFile, `[MAIN EXIT] Backend exited code=${code} signal=${signal}\n`);
    } catch (e) {}
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1220,
    height: 800,
    minWidth: 980,
    minHeight: 650,
    title: 'Dialtone - Cellular Communication',
    backgroundColor: '#090a10',
    autoHideMenuBar: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  const indexPath = path.join(__dirname, 'ui', 'index.html');
  mainWindow.loadFile(indexPath);

  mainWindow.webContents.on('console-message', (event, level, message, line, sourceId) => {
    console.log(`[UI CONSOLE ${level}] ${message} (${path.basename(sourceId)}:${line})`);
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  createWindow();
  checkBackendReady((ready) => {
    if (!ready) {
      console.log('Starting Dialtone Python backend...');
      startBackend();
    } else {
      console.log('Dialtone Backend already active on port 8765.');
    }
  });
});

app.on('window-all-closed', () => {
  if (pythonProcess && pythonProcess.pid) {
    try {
      spawn('taskkill', ['/pid', pythonProcess.pid.toString(), '/f', '/t'], { windowsHide: true });
    } catch (e) {}
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
