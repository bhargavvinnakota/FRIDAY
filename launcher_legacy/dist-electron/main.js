"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const path = __importStar(require("path"));
const child_process_1 = require("child_process");
const electron_is_dev_1 = __importDefault(require("electron-is-dev"));
let mainWindow = null;
let pythonProcess = null;
let tray = null;
function createWindow() {
    const primaryDisplay = electron_1.screen.getPrimaryDisplay();
    const { width, height } = primaryDisplay.workAreaSize;
    mainWindow = new electron_1.BrowserWindow({
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
    const startUrl = electron_is_dev_1.default
        ? 'http://localhost:5173'
        : `file://${path.join(__dirname, '../dist/index.html')}`;
    mainWindow.loadURL(startUrl);
    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}
function startPythonBackend() {
    const pythonPath = '/Users/bhargav/AI/friday/venv/bin/python3';
    const scriptPath = path.join(electron_1.app.getAppPath(), '..', 'senses', 'v2_voice_streaming.py');
    console.log(`Starting Python backend: ${pythonPath} ${scriptPath}`);
    pythonProcess = (0, child_process_1.spawn)(pythonPath, [scriptPath], {
        env: { ...process.env, PYTHONUNBUFFERED: '1' },
        cwd: path.join(electron_1.app.getAppPath(), '..'),
    });
    pythonProcess.stdout?.on('data', (data) => {
        const output = data.toString();
        console.log(`Python: ${output}`);
        if (output.includes('🎙️ Friday \'Neural Reflex\' Active')) {
            mainWindow?.webContents.send('friday-status', 'listening');
        }
        else if (output.includes('👤 You:')) {
            const text = output.split('👤 You:')[1].trim();
            mainWindow?.webContents.send('friday-input', text);
            mainWindow?.webContents.send('friday-status', 'thinking');
        }
        else if (output.includes('🧠 Friday Thinking...')) {
            mainWindow?.webContents.send('friday-status', 'thinking');
        }
        else if (output.includes('🎙️ Friday:')) {
            const parts = output.split('🎙️ Friday:');
            const text = parts[parts.length - 1].trim();
            mainWindow?.webContents.send('friday-status', 'speaking');
            if (text)
                mainWindow?.webContents.send('friday-output', text);
        }
        else if (output.includes('DONE_RESPONSE')) {
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
electron_1.app.whenReady().then(() => {
    createWindow();
    startPythonBackend();
    // Tray Icon
    const icon = electron_1.nativeImage.createEmpty();
    tray = new electron_1.Tray(icon);
    const contextMenu = electron_1.Menu.buildFromTemplate([
        { label: 'Quit Friday', click: () => electron_1.app.quit() }
    ]);
    tray.setToolTip('Friday Assistant');
    tray.setContextMenu(contextMenu);
});
electron_1.app.on('window-all-closed', () => {
    if (process.platform !== 'darwin')
        electron_1.app.quit();
});
electron_1.app.on('will-quit', () => {
    if (pythonProcess) {
        pythonProcess.kill();
    }
});
