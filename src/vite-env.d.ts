/// <reference types="vite/client" />

interface DesktopApi {
  isAdmin: () => Promise<boolean>
  elevate: () => Promise<boolean>
  openPath: (targetPath: string) => Promise<string>
  getBackendUrl: () => Promise<string>
  getApiToken?: () => Promise<string>
  openDiskDetail?: (deviceId: string) => Promise<boolean>
}

declare global {
  interface Window {
    desktopApi?: DesktopApi
  }
}

export {}
