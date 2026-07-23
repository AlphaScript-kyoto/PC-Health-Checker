/// <reference types="vite/client" />

interface DesktopApi {
  elevate: () => Promise<boolean>
  openPath: (targetPath: string) => Promise<string>
  getBackendUrl: () => Promise<string>
}

declare global {
  interface Window {
    desktopApi?: DesktopApi
  }
}

export {}
