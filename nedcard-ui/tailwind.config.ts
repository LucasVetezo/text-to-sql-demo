/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        ned: {
          green:  '#007B40',
          mid:    '#009E52',
          lite:   '#00C66A',
          gold:   '#C9A84C',
          dark:   '#0A1A10',
          dark2:  '#112018',
          slate:  '#1E3329',
          muted:  '#5A8070',
          off:    '#F4F8F5',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'system-ui', '-apple-system', 'sans-serif'],
      },
      keyframes: {
        fadeUp: {
          '0%':   { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
        pulse2: {
          '0%, 100%': { opacity: '1' },
          '50%':       { opacity: '0.4' },
        },
        ringPulse: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(0,198,106,0)',    borderColor: 'rgba(0,198,106,0.08)' },
          '50%':       { boxShadow: '0 0 40px 12px rgba(0,198,106,0.18)', borderColor: 'rgba(0,198,106,0.35)' },
        },
        typewriter: {
          '0%':   { width: '0' },
          '100%': { width: '100%' },
        },
        blink: {
          '0%, 100%': { borderColor: 'transparent' },
          '50%':       { borderColor: '#00C66A' },
        },
        scaleIn: {
          '0%':   { transform: 'scale(0.9)', opacity: '0' },
          '100%': { transform: 'scale(1)',   opacity: '1' },
        },
      },
      animation: {
        'fade-up':    'fadeUp 0.6s ease forwards',
        'fade-in':    'fadeIn 0.5s ease forwards',
        'ring-pulse': 'ringPulse 3.5s ease-in-out infinite',
        'scale-in':   'scaleIn 0.4s ease forwards',
      },
    },
  },
  plugins: [],
}
