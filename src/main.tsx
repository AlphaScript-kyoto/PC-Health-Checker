import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { DiskDetailApp } from './DiskDetailApp'
import './styles/global.css'

const params = new URLSearchParams(window.location.search)
const view = params.get('view')
const deviceId = params.get('id') || ''

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {view === 'disk' && deviceId ? <DiskDetailApp deviceId={deviceId} /> : <App />}
  </StrictMode>,
)
