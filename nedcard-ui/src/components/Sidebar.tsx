import { NavLink, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  LayoutDashboard,
  CreditCard,
  ShieldAlert,
  BarChart3,
  Mic,
  LogOut,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../context/AuthContext'
import { useNavigate } from 'react-router-dom'

const MODULES = [
  {
    path: '/dashboard',
    icon: LayoutDashboard,
    label: 'Dashboard',
    accent: '#00C66A',
  },
  {
    path: '/credit',
    icon: CreditCard,
    label: 'Credit Intelligence',
    accent: '#00C66A',
  },
  {
    path: '/fraud',
    icon: ShieldAlert,
    label: 'Fraud Detection',
    accent: '#E07060',
  },
  {
    path: '/sentiment',
    icon: BarChart3,
    label: 'Social Sentiment',
    accent: '#7EB8DF',
  },
  {
    path: '/speech',
    icon: Mic,
    label: 'CX & Speech',
    accent: '#BF9FDF',
  },
]

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

export default function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <motion.aside
      animate={{ width: collapsed ? 68 : 240 }}
      transition={{ type: 'spring', stiffness: 300, damping: 28 }}
      className="flex-shrink-0 h-screen flex flex-col bg-ned-dark2 border-r border-white/[0.06]
                 relative z-20 overflow-hidden"
    >
      {/* ── Logo ──────────────────────────────────────────── */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-white/[0.05]">
        <div className="flex-shrink-0 w-8 h-8 bg-ned-green rounded-lg flex items-center justify-center">
          <span className="text-white font-black text-sm leading-none">N</span>
        </div>
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ delay: 0.1 }}
          >
            <p className="text-white font-bold text-sm leading-none tracking-tight">NedCard</p>
            <p className="text-ned-muted text-[10px] tracking-widest uppercase leading-none mt-0.5">
              Intelligent Suite
            </p>
          </motion.div>
        )}
      </div>

      {/* ── Nav ───────────────────────────────────────────── */}
      <nav className="flex-1 overflow-y-auto px-2 py-4 space-y-1">
        {!collapsed && (
          <p className="text-ned-muted text-[10px] font-semibold tracking-widest uppercase px-3 mb-3">
            Modules
          </p>
        )}
        {MODULES.map(m => {
          const Icon = m.icon
          const active = location.pathname === m.path ||
                         (m.path !== '/dashboard' && location.pathname.startsWith(m.path))
          return (
            <NavLink
              key={m.path}
              to={m.path}
              className={clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium',
                'transition-all duration-200 cursor-pointer w-full',
                active
                  ? 'text-white bg-ned-slate/70 border border-white/[0.08]'
                  : 'text-ned-muted hover:text-white hover:bg-ned-slate/40'
              )}
              title={collapsed ? m.label : undefined}
            >
              <Icon
                className="flex-shrink-0 w-[18px] h-[18px]"
                style={{ color: active ? m.accent : undefined }}
              />
              {!collapsed && (
                <motion.span
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.08 }}
                  className="truncate"
                >
                  {m.label}
                </motion.span>
              )}
              {active && !collapsed && (
                <span
                  className="ml-auto w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{ background: m.accent }}
                />
              )}
            </NavLink>
          )
        })}
      </nav>

      {/* ── Footer: user + actions ─────────────────────────── */}
      <div className="border-t border-white/[0.05] px-2 py-3 space-y-1">
        {/* User info */}
        {!collapsed && user && (
          <div className="flex items-center gap-3 px-3 py-2 mb-1">
            <div className="w-7 h-7 rounded-full bg-ned-green/30 border border-ned-lite/30
                            flex items-center justify-center flex-shrink-0">
              <span className="text-ned-lite text-xs font-bold">
                {user.name.charAt(0).toUpperCase()}
              </span>
            </div>
            <div className="min-w-0">
              <p className="text-white text-xs font-medium truncate">{user.name}</p>
              <p className="text-ned-muted text-[10px] truncate capitalize">{user.role}</p>
            </div>
          </div>
        )}

        {/* Logout */}
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium w-full
                     text-ned-muted hover:text-red-400 hover:bg-red-400/10 transition-all duration-200"
          title={collapsed ? 'Sign out' : undefined}
        >
          <LogOut className="w-[18px] h-[18px] flex-shrink-0" />
          {!collapsed && (
            <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              Sign out
            </motion.span>
          )}
        </button>
      </div>

      {/* ── Collapse toggle ────────────────────────────────── */}
      <button
        onClick={onToggle}
        className="absolute -right-3 top-[72px] w-6 h-6 rounded-full
                   bg-ned-slate border border-white/10
                   flex items-center justify-center
                   text-ned-muted hover:text-white hover:border-ned-lite/40
                   transition-all duration-200 z-30"
      >
        {collapsed
          ? <ChevronRight className="w-3 h-3" />
          : <ChevronLeft className="w-3 h-3" />}
      </button>
    </motion.aside>
  )
}
