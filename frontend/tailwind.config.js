/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        aqua: {
          bg: '#F5FAFA',
          card: '#FFFFFF',
          primary: '#16B89A',
          deep: '#087F70',
          soft: '#DDF7EF',
          blue: '#55BDEB',
          'deep-blue': '#258FC7',
          'soft-blue': '#E2F4FC',
          text: '#172B35',
          muted: '#6B818B',
          border: '#E1ECEE',
        },
        brand: {
          50: '#F5FAFA',
          100: '#DDF7EF',
          200: '#BAEFE2',
          300: '#7FE2CD',
          400: '#43CEB5',
          500: '#16B89A',
          600: '#0F967D',
          700: '#087F70',
          800: '#066357',
          900: '#172B35',
        }
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgba(23, 43, 53, 0.04), 0 1px 2px -1px rgba(23, 43, 53, 0.02)',
        'card-hover': '0 4px 12px -2px rgba(23, 43, 53, 0.06), 0 2px 4px -1px rgba(23, 43, 53, 0.03)',
        'aqua-glow': '0 0 20px -2px rgba(22, 184, 154, 0.3)',
        'blue-glow': '0 0 20px -2px rgba(85, 189, 235, 0.3)',
      }
    },
  },
  plugins: [],
}
