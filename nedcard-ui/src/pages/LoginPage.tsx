import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Mail, Lock, ChevronRight, Eye, EyeOff, User } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import clsx from 'clsx'

const ROLES = [
  { value: 'analyst',   label: 'Data Analyst' },
  { value: 'executive', label: 'Executive / Leadership' },
  { value: 'agent',     label: 'Call Centre Agent' },
  { value: 'admin',     label: 'Administrator' },
]

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()

  const [name,     setName]     = useState('')
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [role,     setRole]     = useState<string>('analyst')
  const [showPass, setShowPass] = useState(false)
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState('')

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (!name.trim()) { setError('Please enter your name'); return }
    if (!email.includes('@')) { setError('Enter a valid email'); return }
    if (password.length < 4) { setError('Password must be at least 4 characters'); return }

    setLoading(true)
    // Simulate auth latency (replace with real SSO/OAuth endpoint in production)
    await new Promise(r => setTimeout(r, 900))

    login({
      name: name.trim().split(' ')[0],   // first name for greeting
      email,
      role: role as 'analyst' | 'executive' | 'agent' | 'admin',
    })
    navigate('/welcome')
  }

  return (
    <div className="min-h-screen bg-ned-dark flex items-stretch overflow-hidden">
      {/* ── Left panel: brand visual ─────────────────────── */}
      <div className="hidden lg:flex flex-col justify-between w-[52%] relative overflow-hidden
                      bg-gradient-to-br from-ned-dark via-ned-dark2 to-ned-dark p-14">
        {/* Decorative radial glow */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-[-80px] right-[-80px] w-[500px] h-[500px] rounded-full
                          bg-[radial-gradient(circle,rgba(0,198,106,0.12)_0%,transparent_65%)]" />
          <div className="absolute bottom-[-60px] left-[-60px] w-[360px] h-[360px] rounded-full
                          bg-[radial-gradient(circle,rgba(0,123,64,0.10)_0%,transparent_65%)]" />
        </div>

        {/* Top: wordmark */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="w-9 h-9 bg-ned-green rounded-lg flex items-center justify-center">
            <span className="text-white font-black text-base leading-none">N</span>
          </div>
          <div>
            <p className="text-white font-bold text-sm tracking-tight leading-none">NedCard</p>
            <p className="text-ned-muted text-[10px] tracking-widest uppercase leading-none mt-0.5">Intelligent Suite</p>
          </div>
        </div>

        {/* Centre: animated ring + tagline */}
        <div className="relative z-10 flex flex-col items-center gap-14">
          {/* Pulsing ring */}
          <div className="relative flex items-center justify-center animate-ring-pulse"
               style={{ width: 260, height: 260, borderRadius: '50%',
                        border: '1px solid rgba(0,198,106,0.12)',
                        background: 'radial-gradient(circle,rgba(0,198,106,0.10) 0%,rgba(0,123,64,0.04) 50%,transparent 70%)' }}>
            <div style={{ width: 200, height: 200, borderRadius: '50%',
                          border: '1px solid rgba(0,198,106,0.18)',
                          background: 'radial-gradient(circle,rgba(0,198,106,0.15) 0%,transparent 70%)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <motion.img
                src="/logo1.png"
                alt="NedCard AI"
                style={{ width: 200, height: 200, objectFit: 'contain' }}
                animate={{ opacity: [0.65, 1, 0.65] }}
                transition={{ duration: 3.5, ease: 'easeInOut', repeat: Infinity, repeatType: 'loop' }}
              />
            </div>
          </div>

          <div className="text-center max-w-xs">
            <h2 className="text-white text-3xl font-extrabold leading-tight tracking-tight mb-3">
              The AI<br />
              <span className="text-ned-lite">Powered Analytics <br />Platform</span>
            </h2>
            <p className="text-ned-muted text-sm leading-relaxed">
              Interrogate complex data in plain English and 
              uncover insights in seconds.
            </p>
          </div>
        </div>

        {/* Bottom: capability pills */}
        <div className="relative z-10 flex flex-wrap gap-2">
          {['Credit Risk','Fraud Detection','Social Sentiment','CX Insights'].map(t => (
            <span key={t} className="tag-pill">{t}</span>
          ))}
        </div>
      </div>

      {/* ── Right panel: login form ──────────────────────── */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 sm:px-12 lg:px-20
                      bg-gradient-to-br from-ned-dark2 to-ned-dark">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55 }}
          className="w-full max-w-md"
        >
          {/* Mobile: wordmark */}
          <div className="flex lg:hidden items-center gap-3 mb-10">
            <div className="w-8 h-8 bg-ned-green rounded-lg flex items-center justify-center">
              <span className="text-white font-black text-sm">N</span>
            </div>
            <div>
              <p className="text-white font-bold text-sm">NedCard Intelligent Suite</p>
              <p className="text-ned-muted text-[10px] tracking-widest uppercase">AI-Powered Analytics</p>
            </div>
          </div>

          <h1 className="text-white text-2xl font-bold mb-1">Sign in</h1>
          <p className="text-ned-muted text-sm mb-8">Enter your credentials to access the platform.</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name */}
            <div>
              <label className="block text-xs font-medium text-ned-muted mb-1.5 tracking-wide uppercase">
                Display name
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ned-muted" />
                <input
                  className="ned-input pl-10"
                  placeholder="Your name"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  autoComplete="given-name"
                />
              </div>
            </div>

            {/* Email */}
            <div>
              <label className="block text-xs font-medium text-ned-muted mb-1.5 tracking-wide uppercase">
                Work email
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ned-muted" />
                <input
                  type="email"
                  className="ned-input pl-10"
                  placeholder="you@nedbank.co.za"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  autoComplete="email"
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label className="block text-xs font-medium text-ned-muted mb-1.5 tracking-wide uppercase">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ned-muted" />
                <input
                  type={showPass ? 'text' : 'password'}
                  className="ned-input pl-10 pr-10"
                  placeholder="••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPass(p => !p)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-ned-muted hover:text-white transition-colors"
                >
                  {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Role */}
            <div>
              <label className="block text-xs font-medium text-ned-muted mb-1.5 tracking-wide uppercase">
                Your role
              </label>
              <div className="flex flex-wrap gap-2">
                {ROLES.map(r => (
                  <button
                    key={r.value}
                    type="button"
                    onClick={() => setRole(r.value)}
                    className={clsx(
                      'px-3 py-1.5 rounded-lg text-xs font-medium border transition-all duration-200',
                      role === r.value
                        ? 'bg-ned-green/25 border-ned-lite/40 text-ned-lite'
                        : 'bg-white/[0.04] border-white/10 text-ned-muted hover:border-white/25 hover:text-white'
                    )}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Error */}
            {error && (
              <motion.p
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-red-400 text-xs bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2"
              >
                {error}
              </motion.p>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="btn-primary mt-2"
            >
              {loading ? (
                <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
                </svg>
              ) : (
                <>Access Platform <ChevronRight className="w-4 h-4" /></>
              )}
            </button>
          </form>

          <p className="text-ned-muted text-xs text-center mt-8 leading-relaxed">
            This is a secured internal portal. Unauthorised access is prohibited.<br />
            Production deployments connect to Nedbank's SSO / Azure AD.
          </p>
        </motion.div>
      </div>
    </div>
  )
}
