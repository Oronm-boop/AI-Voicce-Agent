/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/renderer/index.html',
    './src/renderer/src/**/*.{vue,ts,tsx,js,jsx}'
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        'surface': '#f8f9fa',
        'surface-dim': '#d9dadb',
        'surface-bright': '#f8f9fa',
        'surface-container-lowest': '#ffffff',
        'surface-container-low': '#f3f4f5',
        'surface-container': '#edeeef',
        'surface-container-high': '#e7e8e9',
        'surface-container-highest': '#e1e3e4',
        'on-surface': '#191c1d',
        'on-surface-variant': '#44474c',
        'inverse-surface': '#2e3132',
        'inverse-on-surface': '#f0f1f2',
        'outline': '#75777d',
        'outline-variant': '#c5c6cc',
        'surface-tint': '#555f70',
        'primary': '#212b3a',
        'on-primary': '#ffffff',
        'primary-container': '#374151',
        'on-primary-container': '#a3adc0',
        'inverse-primary': '#bdc7db',
        'secondary': '#585f6c',
        'on-secondary': '#ffffff',
        'secondary-container': '#dce2f3',
        'on-secondary-container': '#5e6572',
        'tertiary': '#362811',
        'on-tertiary': '#ffffff',
        'tertiary-container': '#4e3e25',
        'on-tertiary-container': '#c0a989',
        'error': '#ba1a1a',
        'on-error': '#ffffff',
        'error-container': '#ffdad6',
        'on-error-container': '#93000a',
        'primary-fixed': '#d9e3f7',
        'primary-fixed-dim': '#bdc7db',
        'on-primary-fixed': '#121c2a',
        'on-primary-fixed-variant': '#3d4757',
        'secondary-fixed': '#dce2f3',
        'secondary-fixed-dim': '#c0c7d6',
        'on-secondary-fixed': '#151c27',
        'on-secondary-fixed-variant': '#404754',
        'tertiary-fixed': '#f8dfbc',
        'tertiary-fixed-dim': '#dbc3a2',
        'on-tertiary-fixed': '#261905',
        'on-tertiary-fixed-variant': '#55442b',
        'background': '#f8f9fa',
        'on-background': '#191c1d',
        'surface-variant': '#e1e3e4'
      },
      borderRadius: {
        DEFAULT: '0.25rem',
        sm: '0.25rem',
        md: '0.75rem',
        lg: '0.5rem',
        xl: '0.75rem',
        full: '9999px'
      },
      spacing: {
        unit: '8px',
        'container-padding': '32px',
        gutter: '24px',
        'element-gap': '16px',
        'stack-tight': '4px'
      },
      fontFamily: {
        'display-lg': ['Hanken Grotesk', 'sans-serif'],
        'headline-md': ['Hanken Grotesk', 'sans-serif'],
        'label-sm': ['Hanken Grotesk', 'sans-serif'],
        'title-sm': ['Noto Sans SC', 'sans-serif'],
        'body-md': ['Noto Sans SC', 'sans-serif'],
        'body-lg': ['Noto Sans SC', 'sans-serif']
      },
      fontSize: {
        'display-lg': ['32px', { lineHeight: '40px', letterSpacing: '-0.02em', fontWeight: '600' }],
        'headline-md': ['24px', { lineHeight: '32px', letterSpacing: '-0.01em', fontWeight: '500' }],
        'title-sm': ['18px', { lineHeight: '26px', fontWeight: '500' }],
        'body-lg': ['16px', { lineHeight: '24px', fontWeight: '400' }],
        'body-md': ['14px', { lineHeight: '22px', fontWeight: '400' }],
        'label-sm': ['12px', { lineHeight: '16px', letterSpacing: '0.05em', fontWeight: '500' }]
      },
      keyframes: {
        wave: {
          '0%': { height: '10px' },
          '100%': { height: '60px' }
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' }
        },
        fadeInUp: {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to: { opacity: '1', transform: 'translateY(0)' }
        }
      },
      animation: {
        wave: 'wave 1.2s ease-in-out infinite alternate',
        shimmer: 'shimmer 2s infinite',
        'fade-in-up': 'fadeInUp 0.6s ease-out forwards'
      }
    }
  },
  plugins: []
}
