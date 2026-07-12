/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "PingFang SC", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      colors: {
        gpt: {
          sidebar: "#f9fafb",
          "sidebar-dark": "#171717",
          main: "#ffffff",
          "main-dark": "#212121",
          "user-msg": "#f4f4f4",
          "user-msg-dark": "#2f2f2f",
          accent: "#10a37f",
          "accent-hover": "#0d8c6d",
        },
      },
      borderRadius: {
        gpt: "0.75rem",
      },
      boxShadow: {
        gpt: "0 0 0 1px rgba(0,0,0,0.08), 0 1px 3px rgba(0,0,0,0.04)",
        "gpt-hover": "0 0 0 1px rgba(0,0,0,0.12), 0 2px 6px rgba(0,0,0,0.06)",
      },
      animation: {
        "fade-in": "fadeIn 150ms ease-out",
        "slide-up": "slideUp 150ms ease-out",
        "pulse-dot": "pulseDot 1.4s ease-in-out infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulseDot: {
          "0%, 80%, 100%": { opacity: "0.2" },
          "40%": { opacity: "1" },
        },
      },
    },
  },
  plugins: [],
};