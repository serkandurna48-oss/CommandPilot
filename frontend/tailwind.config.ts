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
          // Exact Higgsfield spec (04-design-system/01-brand-color.png) —
          // 500/600 already matched the prior scale precisely, the rest are
          // now aligned too.
          50:  "#f7d9b3",
          100: "#f2c79a",
          200: "#e7b07a",
          300: "#d99b60",
          400: "#c8894e",
          500: "#b5733f",
          600: "#9c5e33",
          700: "#7f4b28",
          800: "#62381e",
          900: "#4a2b16",
        },
        // Statusfarben — bewusst getrennte Farbfamilie von brand/bronze,
        // niemals als Ersatz für Bronze verwendet (siehe globals.css).
        status: {
          success: "#22c55e",
          warning: "#f59e0b", // Higgsfield spec value (was #eab308)
          danger:  "#ef4444",
          info:    "#3b82f6",
          neutral: "#6b7280", // Higgsfield spec's 4th status color (inactive/disabled)
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
