export default {
  content: ["./src/**/*.{astro,html,js,jsx,md,mdx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        serif: ['"Noto Serif KR"', '"Fraunces"', "ui-serif", "Georgia", "serif"],
        sans: [
          "Pretendard",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      colors: {
        ink: {
          DEFAULT: "#0d0d0c",
          soft: "#2a2a28",
          muted: "#6b6a65",
        },
        paper: {
          DEFAULT: "#f6f3ec",
          deep: "#efeadf",
          line: "#d9d3c4",
        },
        accent: {
          DEFAULT: "#b8860b",
          dim: "#8a6508",
        },
        bull: "#2d5d3a",
        bear: "#a32d2d",
      },
      letterSpacing: {
        tightest: "-0.04em",
      },
    },
  },
  plugins: [],
};
