import { app, BrowserWindow, ipcMain, globalShortcut, Tray, Menu, nativeImage, screen } from 'electron';
import * as path from 'path';
import { spawn, ChildProcess } from 'child_process';
import isDev from 'electron-is-dev';

let mainWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;
let tray: Tray | null = null;

function createWindow() {
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width, height } = primaryDisplay.workAreaSize;

  mainWindow = new BrowserWindow({
    width: width,
    height: height,
    x: 0,
    y: 0,
    show: true,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // Make the window click-through
  mainWindow.setIgnoreMouseEvents(true, { forward: true });

  const startUrl = isDev 
    ? 'http://localhost:5173' 
    : `file://${path.join(__dirname, '../dist/index.html')}`;

  mainWindow.loadURL(startUrl);

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function startPythonBackend() {
  const pythonPath = '/Users/bhargav/AI/friday/venv/bin/python3';
  const scriptPath = path.join(app.getAppPath(), '..', 'senses', 'v2_voice_streaming.py');
  
  console.log(`Starting Python backend: ${pythonPath} ${scriptPath}`);

  pythonProcess = spawn(pythonPath, [scriptPath], {
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
    cwd: path.join(app.getAppPath(), '..'),
  });

  pythonProcess.stdout?.on('data', (data) => {
    const output = data.toString();
    console.log(`Python: ${output}`);
    
    if (output.includes('🎙️ Friday \'Neural Reflex\' Active')) {
      mainWindow?.webContents.send('friday-status', 'listening');
    } else if (output.includes('👤 You:')) {
      const text = output.split('👤 You:')[1].trim();
      mainWindow?.webContents.send('friday-input', text);
      mainWindow?.webContents.send('friday-status', 'thinking');
    } else if (output.includes('🧠 Friday Thinking...')) {
      mainWindow?.webContents.send('friday-status', 'thinking');
    } else if (output.includes('🎙️ Friday:')) {
      const parts = output.split('🎙️ Friday:');
      const text = parts[parts.length - 1].trim();
      mainWindow?.webContents.send('friday-status', 'speaking');
      if (text) mainWindow?.webContents.send('friday-output', text);
    } else if (output.includes('DONE_RESPONSE')) {
      mainWindow?.webContents.send('friday-status', 'listening');
    }
  });

  pythonProcess.stderr?.on('data', (data) => {
    console.error(`Python Error: ${data.toString()}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`Python process exited with code ${code}`);
  });
}

app.whenReady().then(() => {
  createWindow();
  startPythonBackend();

  // Tray Icon
  const icon = nativeImage.createEmpty();
  tray = new Tray(icon);
  const contextMenu = Menu.buildFromTemplate([
    { label: 'Quit Friday', click: () => app.quit() }
  ]);
  tray.setToolTip('Friday Assistant');
  tray.setContextMenu(contextMenu);
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('will-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
});
