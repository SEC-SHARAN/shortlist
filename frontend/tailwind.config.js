/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ['"Schibsted Grotesk"', "system-ui", "sans-serif"], mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"] },
      colors: {
        ink: { DEFAULT: "#16203A", soft: "#4A5470", mute: "#7C85A0" },
        paper: { DEFAULT: "#F4F5F8", card: "#FFFFFF", line: "#E3E6EE" },
        accent: { DEFAULT: "#3B4BD8", soft: "#E9ECFC", dark: "#2B38A8" },
        good: { DEFAULT: "#1E8E5A", soft: "#E3F4EB" },
        warn: { DEFAULT: "#A86A0F", soft: "#FBF0DA" },
        bad: { DEFAULT: "#B4412F", soft: "#FBE9E5" },
      },
    },
  },
  plugins: [],
};
