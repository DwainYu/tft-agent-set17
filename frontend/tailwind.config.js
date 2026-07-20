/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        tft: {
          gold: '#E8B84D',
          goldDark: '#C9982E',
          blue: '#2E86DE',
          dark: '#1A1A2E',
          card: '#23233A',
          border: '#3A3A5A',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
