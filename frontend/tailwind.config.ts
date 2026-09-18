import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Gedämpftes Steel-Blue — bewusst desaturiert (H~207° S~33%) gegen
        // das vivide #3b82f6 (H~217° S~91%) von LIFE_AREA_COLORS.work in
        // types/index.ts, damit beide nebeneinander eindeutig unterscheidbar
        // bleiben (JARVIS-D1, Serkans Bedingung "ein Blau, nicht zwei").
        brand: {
          50:  "#eef3f8",
          100: "#dce7f0",
          200: "#b9cee0",
          300: "#93b1cb",
          400: "#6f96b4",
          500: "#4f7a9c",
          600: "#3f6483",
          700: "#33506a",
          800: "#293f52",
          900: "#212f3b",
        },
        status: {
          success: "#22c55e",
          warning: "#f59e0b",
          danger:  "#ef4444",
          neutral: "#64748b",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
