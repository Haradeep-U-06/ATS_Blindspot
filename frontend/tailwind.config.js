/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: "var(--color-primary)",
        secondary: "var(--color-secondary)",
        soft: "var(--color-soft)",
        cream: "var(--color-cream)",
        dark: "var(--color-dark)",
        mid: "var(--color-mid)",
        light: "var(--color-light)",
        error: "var(--color-error)",
        warning: "var(--color-warning)",
        success: "var(--color-success)",
      },
      fontFamily: {
        heading: ['"Playfair Display"', "serif"],
        body: ['"DM Sans"', "sans-serif"],
        mono: ['"JetBrains Mono"', "monospace"],
      },
      keyframes: {
        pulseDot: {
          '0%, 100%': { transform: 'scale(0.8)', opacity: '0.5' },
          '50%': { transform: 'scale(1.2)', opacity: '1' },
        }
      },
      animation: {
        pulseDot: 'pulseDot 1.5s ease-in-out infinite',
      }
    },
  },
  plugins: [],
}
