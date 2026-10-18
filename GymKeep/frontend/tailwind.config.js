/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Rojo del logo de GymKeep (el 600 es el color de accion principal; con texto blanco
        // cumple contraste AA). El negro del logo es `bg-black`.
        brand: {
          50: '#fff1f2',
          100: '#ffe1e3',
          200: '#ffc7cb',
          300: '#ff9ea6',
          400: '#ff5a68',
          500: '#f4212f',
          600: '#e50914',
          700: '#b9070f',
          800: '#8f0a12',
          900: '#730d14',
        },
      },
      fontFamily: {
        // Titulos: condensada e inclinada, en linea con la tipografia deportiva del logo.
        display: ['"Barlow Condensed"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
