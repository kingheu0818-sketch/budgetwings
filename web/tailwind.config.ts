import type {Config} from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#111827',
        paper: '#f8fafc',
        mint: '#0f766e',
        coral: '#e11d48',
        gold: '#ca8a04'
      }
    }
  },
  plugins: [require('@tailwindcss/typography')]
};

export default config;
