"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
electron_1.contextBridge.exposeInMainWorld('electron', {
    onFridayStatus: (callback) => electron_1.ipcRenderer.on('friday-status', (_, status) => callback(status)),
    onFridayInput: (callback) => electron_1.ipcRenderer.on('friday-input', (_, text) => callback(text)),
    onFridayOutput: (callback) => electron_1.ipcRenderer.on('friday-output', (_, text) => callback(text)),
});
