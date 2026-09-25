/** @type {import('tailwindcss').Config} */
// Aura · Tailwind preset — Deep Tide palette
// Drop this into your tailwind.config.js or extend from it:
//   module.exports = { presets: [require('./brand/tokens/tailwind.config.js')] }

module.exports = {
  theme: {
    extend: {
      colors: {
        aura: {
          bg2:    '#0F2A30',
          bg:     '#173D45',
          bg3:    '#1F4A54',
          bg4:    '#2A5862',
          ink:    '#F2EDE0',
          ink2:   '#B8B0A0',
          muted:  '#7A7468',
          accent: '#E8B86D',
          dim:    '#B89348',
          success:'#7FB89B',
          warn:   '#D4A85A',
          error:  '#C97A6B',
          info:   '#6FA5B8',
        },
      },
      fontFamily: {
        display: ['"DM Serif Display"', 'Georgia', 'serif'],
        serif:   ['"Instrument Serif"', 'Georgia', 'serif'],
        sans:    ['Outfit', 'system-ui', 'sans-serif'],
        mono:    ['"JetBrains Mono"', '"SF Mono"', 'monospace'],
      },
      borderRadius: {
        sm: '4px',
        md: '8px',
        lg: '16px',
        xl: '24px',
      },
      transitionTimingFunction: {
        'aura': 'cubic-bezier(0.2, 0.7, 0.2, 1)',
      },
      boxShadow: {
        'aura-sm': '0 2px 8px rgba(0,0,0,0.08)',
        'aura':    '0 8px 24px -4px rgba(0,0,0,0.18)',
        'aura-lg': '0 24px 60px -12px rgba(0,0,0,0.30)',
        'aura-accent': '0 16px 48px -8px rgba(232,184,109,0.25)',
      },
    },
  },
};
