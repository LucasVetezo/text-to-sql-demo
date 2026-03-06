import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Bell } from 'lucide-react'
import Sidebar from './Sidebar'
import { useAuth } from '../context/AuthContext'

const BREADCRUMBS: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/credit':    'Credit Risk Intelligence',
  '/fraud':     'Fraud Detection',
  '/sentiment': 'Social Sentiment Analysis',
  '/speech':    'Speech & CX Insights',
}

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false)
  const { user } = useAuth()
  const location = useLocation()
  const crumb = BREADCRUMBS[location.pathname] ?? 'NedCard'

  return (
    <div className="flex h-screen overflow-hidden bg-ned-dark">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(p => !p)} />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* ── Top bar ──────────────────────────────────────── */}
        <header className="flex-shrink-0 flex items-center justify-between
                           h-14 px-6 border-b border-white/[0.05] bg-ned-dark2/60 backdrop-blur-sm">
          {/* Breadcrumb */}
          <div className="flex items-center gap-2 text-sm">
            <span className="text-ned-muted">NedCard</span>
            <span className="text-ned-muted/50">/</span>
            <span className="text-white font-medium">{crumb}</span>
          </div>

          {/* Right actions */}
          <div className="flex items-center gap-3">
            {/* Notification bell */}
            <button className="relative w-8 h-8 rounded-lg bg-ned-slate/40 border border-white/10
                               flex items-center justify-center text-ned-muted hover:text-white
                               transition-all duration-200">
              <Bell className="w-4 h-4" />
              <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-ned-lite" />
            </button>

            {/* Avatar */}
            {user && (
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-full bg-ned-green/30 border border-ned-lite/30
                                flex items-center justify-center">
                  <span className="text-ned-lite text-xs font-bold">
                    {user.name.charAt(0).toUpperCase()}
                  </span>
                </div>
                <div className="hidden sm:block">
                  <p className="text-white text-xs font-medium leading-none">{user.name}</p>
                  <p className="text-ned-muted text-[10px] leading-none mt-0.5 capitalize">{user.role}</p>
                </div>
              </div>
            )}
          </div>
        </header>

        {/* ── Page content ─────────────────────────────────── */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
