import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from '@/lib/AuthContext'
import { LandingPage } from '@/pages/LandingPage'
import { AppShell } from '@/components/ui/AppShell'
import { ServerWakeUp } from '@/components/ui/ServerWakeUp'
import { useHealth } from '@/hooks/useHealth'

// Code-split heavy document and chat pages to keep landing page bundle minimal
const DocumentsPage = lazy(() => import('@/pages/DocumentsPage').then(m => ({ default: m.DocumentsPage })))
const ChatPage = lazy(() => import('@/pages/ChatPage').then(m => ({ default: m.ChatPage })))

export default function App() {
  const { token } = useAuth()
  const { reachable, warmedUp } = useHealth()

  // Unauthenticated users ALWAYS see the LandingPage immediately (0ms blocking)
  if (!token) {
    return (
      <Routes>
        <Route path="/" element={<LandingPage reachable={reachable} warmedUp={warmedUp} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    )
  }

  // Authenticated users waiting for offline backend
  if (!reachable) {
    return <ServerWakeUp checking={false} />
  }

  return (
    <AppShell>
      <Suspense fallback={<div className="skeleton" style={{ height: 180, margin: '2rem' }} />}>
        <Routes>
          <Route path="/" element={<Navigate to="/documents" replace />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/chat/:documentId" element={<ChatPage />} />
          <Route path="*" element={<Navigate to="/documents" replace />} />
        </Routes>
      </Suspense>
    </AppShell>
  )
}

