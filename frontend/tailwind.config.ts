import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Focus Deck (Bronze/Copper) — ersetzt die frühere Indigo-Skala und
        // die verworfene Steel-Blue-Richtung aus JARVIS-D1 (cp-design).
        // brand-600 ist der Standard-Button-Fill (siehe globals.css für den
        // berechneten Kontrast gegen Weiß-Text und den Abstand zu warning).
        brand: {
          50:  "#faf3ec",
          100: "#f0dfc9",
          200: "#e2c29d",
          300: "#d1a374",
          400: "#c0884f",
          500: "#b5733f",
          600: "#9c5e33",
          700: "#7c4a28",
          800: "#5c371e",
          900: "#3d2414",
        },
        // Statusfarben — bewusst getrennte Farbfamilie von brand/bronze,
        // niemals als Ersatz für Bronze verwendet (siehe globals.css).
        status: {
          success: "#22c55e",
          warning: "#eab308",
          danger:  "#ef4444",
          info:    "#3b82f6",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Menlo", "monospace"],
        // Nur für die eine große persönliche/briefingartige Headline pro
        // View (Design-System-Board, Typography-Blatt) — nie für
        // Navigation, Wortmarken oder UI-Standardtext.
        // Quoted: "Source Serif 4" ends in a bare digit, which is not a
        // valid unquoted CSS identifier token. Left unquoted, Tailwind
        // emits `font-family: Source Serif 4, Georgia, serif` — invalid
        // CSS that Chrome silently drops in full, falling back to Inter.
        // Pre-existing bug from Focus Deck Slice 1 (the serif headline
        // never actually rendered as serif in any browser); found and
        // fixed during the Visual Fidelity Sprint.
        serif: ['"Source Serif 4"', "Georgia", "serif"],
      },
    },
  },
  plugins: [],
};

export default config;
