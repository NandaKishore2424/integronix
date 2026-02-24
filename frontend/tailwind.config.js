/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      colors: {
        surface: {
          DEFAULT: '#141926',
          raised: '#1a2035',
          overlay: '#1f2840',
        },
        accent: {
          DEFAULT: '#6366f1',
          light: '#a78bfa',
          bright: '#818cf8',
          glow: 'rgba(99,102,241,0.3)',
        },
        success: { DEFAULT: '#22c55e', light: '#4ade80', muted: 'rgba(34,197,94,0.15)' },
        warning: { DEFAULT: '#f59e0b', light: '#fbbf24', muted: 'rgba(245,158,11,0.15)' },
        danger: { DEFAULT: '#ef4444', light: '#f87171', muted: 'rgba(239,68,68,0.15)' },
        cyan: { DEFAULT: '#06b6d4', light: '#22d3ee' },
        purple: { DEFAULT: '#8b5cf6', light: '#a78bfa' },
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4,0,0.6,1) infinite',
        'spin-slow': 'spin 3s linear infinite',
        'bounce-sm': 'bounceSm 1s ease infinite',
        'fade-in': 'fadeIn 0.4s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
      },
      keyframes: {
        bounceSm: { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-4px)' } },
      },
      backgroundImage: {
        'gradient-accent': 'linear-gradient(135deg, #6366f1, #8b5cf6)',
        'gradient-success': 'linear-gradient(135deg, #22c55e, #4ade80)',
        'gradient-card': 'linear-gradient(145deg, rgba(255,255,255,0.08), rgba(255,255,255,0.03))',
      },
      boxShadow: {
        'glow-sm': '0 0 15px rgba(99,102,241,0.25)',
        'glow-md': '0 0 30px rgba(99,102,241,0.35)',
        'glow-lg': '0 0 50px rgba(99,102,241,0.4)',
        'card': '0 12px 40px rgba(0,0,0,0.45)',
        'inner-top': 'inset 0 1px 0 rgba(255,255,255,0.09)',
      },
    },
  },
  plugins: [],
}
