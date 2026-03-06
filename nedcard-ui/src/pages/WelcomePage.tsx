import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '../context/AuthContext'

const TAGLINE = 'AI-Powered Analytics Platform that lets you interrogate complex data — in plain English — and receive instant insights.'

export default function WelcomePage() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [phase, setPhase] = useState<'ring' | 'greeting' | 'tagline' | 'done'>('ring')
  const [taglineText, setTaglineText] = useState('')

  useEffect(() => {
    // Phase sequence
    const t1 = setTimeout(() => setPhase('greeting'), 700)
    const t2 = setTimeout(() => setPhase('tagline'),  1_800)
    const t3 = setTimeout(() => setPhase('done'),     5_200)
    const t4 = setTimeout(() => navigate('/chat'), 5_600)
    return () => [t1, t2, t3, t4].forEach(clearTimeout)
  }, [navigate])

  // Typewriter effect for tagline
  useEffect(() => {
    if (phase !== 'tagline') return
    let i = 0
    const interval = setInterval(() => {
      i++
      setTaglineText(TAGLINE.slice(0, i))
      if (i >= TAGLINE.length) clearInterval(interval)
    }, 22)
    return () => clearInterval(interval)
  }, [phase])

  return (
    <AnimatePresence>
      <motion.div
        key="welcome"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.5 }}
        className="min-h-screen bg-ned-dark flex flex-col items-center justify-center overflow-hidden relative"
      >
        {/* Radial glow background */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
                          w-[700px] h-[700px] rounded-full
                          bg-[radial-gradient(circle,rgba(0,198,106,0.10)_0%,transparent_65%)]" />
        </div>

        <div className="relative z-10 flex flex-col items-center text-center px-6 max-w-2xl">
          {/* Animated ring with bot */}
          <motion.div
            animate={phase === 'ring'
              ? { scale: [1, 1.06, 1], opacity: 1 }
              : { scale: 0.7, opacity: 0, y: -40 }}
            transition={{ duration: 0.6 }}
            className="mb-12 flex items-center justify-center animate-ring-pulse"
            style={{
              width: 200, height: 200, borderRadius: '50%',
              border: '1px solid rgba(0,198,106,0.15)',
              background: 'radial-gradient(circle,rgba(0,198,106,0.12) 0%,rgba(0,123,64,0.05) 50%,transparent 70%)',
            }}
          >
            <div style={{
              width: 150, height: 150, borderRadius: '50%',
              border: '1px solid rgba(0,198,106,0.22)',
              background: 'radial-gradient(circle,rgba(0,198,106,0.18) 0%,transparent 70%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <img src="/logo1.png" alt="NedCard AI" style={{ width: 120, height: 120, objectFit: 'contain' }} />
            </div>
          </motion.div>

          {/* Greeting */}
          <AnimatePresence>
            {['greeting', 'tagline', 'done'].includes(phase) && (
              <motion.div
                initial={{ opacity: 0, y: 28 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, ease: 'easeOut' }}
                className="mb-6"
              >
                <p className="text-ned-muted text-sm font-medium tracking-widest uppercase mb-4">
                  Welcome back
                </p>
                <h1 className="text-white text-4xl sm:text-5xl lg:text-6xl font-extrabold leading-tight tracking-tight mb-3">
                  Hello,{' '}
                  <span className="text-ned-lite">{user?.name ?? 'there'}</span> 👋
                </h1>
                <h2 className="text-white/70 text-xl sm:text-2xl font-semibold leading-snug">
                  to the{' '}
                  <span className="text-white font-bold">NedCard Intelligent Suite</span>
                </h2>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Typewriter tagline */}
          <AnimatePresence>
            {['tagline', 'done'].includes(phase) && (
              <motion.p
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                className="text-ned-muted text-base sm:text-lg leading-relaxed max-w-xl min-h-[80px]"
              >
                {taglineText}
                {phase === 'tagline' && (
                  <span className="inline-block w-0.5 h-4 bg-ned-lite ml-0.5 animate-pulse align-middle" />
                )}
              </motion.p>
            )}
          </AnimatePresence>

          {/* Loading dots */}
          <AnimatePresence>
            {phase === 'done' && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-10 flex flex-col items-center gap-3"
              >
                <div className="flex items-center gap-2">
                  {[0, 1, 2].map(i => (
                    <div
                      key={i}
                      className="w-2 h-2 rounded-full bg-ned-lite dot-bounce"
                      style={{ animationDelay: `${i * 0.15}s` }}
                    />
                  ))}
                </div>
                <p className="text-ned-muted text-xs tracking-widest uppercase">Launching platform…</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Bottom brand strip */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex items-center gap-2">
          <div className="w-5 h-5 bg-ned-green rounded-md flex items-center justify-center">
            <span className="text-white font-black text-xs">N</span>
          </div>
          <span className="text-ned-muted text-xs tracking-widest uppercase">
            Nedbank · AI-Powered Analytics
          </span>
        </div>
      </motion.div>
    </AnimatePresence>
  )
}
