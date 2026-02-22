import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/global.css'
import '@solana/wallet-adapter-react-ui/styles.css'
import App from './App'
import { SolanaProvider } from './solana/SolanaProvider'

const root = document.getElementById('root')
if (!root) throw new Error('Root element not found')

createRoot(root).render(
  <StrictMode>
    <SolanaProvider>
      <App />
    </SolanaProvider>
  </StrictMode>
)
