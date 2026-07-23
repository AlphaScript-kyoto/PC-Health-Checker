import { contextBridge, ipcRenderer } from 'electron'

export interface DesktopApi {
  isAdmin: () => Promise<boolean>
  elevate: () => Promise<boolean>
  openPath: (targetPath: string) => Promise<string>
  getBackendUrl: () => Promise<string>
}

const api: DesktopApi = {
  isAdmin: () => ipcRenderer.invoke('desktop:is-admin'),
  elevate: () => ipcRenderer.invoke('desktop:elevate'),
  openPath: (targetPath: string) => ipcRenderer.invoke('desktop:openPath', targetPath),
  getBackendUrl: () => ipcRenderer.invoke('desktop:getBackendUrl'),
}

contextBridge.exposeInMainWorld('desktopApi', api)
