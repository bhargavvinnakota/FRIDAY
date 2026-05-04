import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electron', {
  onFridayStatus: (callback: (status: string) => void) => 
    ipcRenderer.on('friday-status', (_, status) => callback(status)),
  onFridayInput: (callback: (text: string) => void) => 
    ipcRenderer.on('friday-input', (_, text) => callback(text)),
  onFridayOutput: (callback: (text: string) => void) => 
    ipcRenderer.on('friday-output', (_, text) => callback(text)),
});
