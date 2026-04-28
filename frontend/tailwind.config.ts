import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        aegis: {
          bg: '#0f172a',
          accent: '#22d3ee',
          amber: '#f59e0b',
          emerald: '#10b981',
          error: '#ef4444',
          purple: '#9333ea',
          indigo: '#4f46e5',
        },
      },
    },
  },
  plugins: [],
};
export default config;
