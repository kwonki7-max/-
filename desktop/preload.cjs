'use strict';
const {contextBridge, ipcRenderer} = require('electron');
contextBridge.exposeInMainWorld('desktop', Object.freeze({
  info: () => ipcRenderer.invoke('desktop:info'),
  retry: () => ipcRenderer.invoke('desktop:retry'),
  minimize: () => ipcRenderer.send('desktop:minimize'),
  maximize: () => ipcRenderer.send('desktop:maximize'),
  close: () => ipcRenderer.send('desktop:close'),
  reload: () => ipcRenderer.invoke('desktop:reload')
}));
