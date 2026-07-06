export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["Inter", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        ink: "#090B10",
        surface: "#111827",
        card: "#171F2B",
        "card-hover": "#1D2736",
        line: "rgba(255,255,255,0.06)",
        "line-strong": "rgba(255,255,255,0.10)",
        "txt-pri": "#F8FAFC",
        "txt-sec": "#AAB6C5",
        "txt-mut": "#7B8794",
        accent: "#22D3EE",
        "accent-2": "#3B82F6",
        success: "#22C55E",
        warning: "#F59E0B",
        danger: "#EF4444",
        violet: "#8B5CF6",
        brand: {
          cyan: "#22D3EE",
          teal: "#3B82F6",
          bg: "#090B10",
          sidebar: "#111827",
          border: "rgba(255,255,255,0.06)",
          bubble: "#171F2B",
          "bubble-user": "#12202E",
          "border-user": "rgba(34,211,238,0.35)",
          muted: "#7B8794",
          mid: "#AAB6C5",
          "text-sec": "#AAB6C5",
          "text-pri": "#F8FAFC",
        },
      },
      borderRadius: {
        card: "18px",
        modal: "24px",
      },
      boxShadow: {
        card: "0 1px 0 rgba(255,255,255,0.04) inset, 0 8px 24px -12px rgba(0,0,0,0.6)",
        "card-lift":
          "0 1px 0 rgba(255,255,255,0.06) inset, 0 16px 40px -16px rgba(0,0,0,0.7)",
        "glow-cyan": "0 0 0 1px rgba(34,211,238,0.28), 0 0 24px -6px rgba(34,211,238,0.35)",
        "glow-soft": "0 0 20px -8px rgba(34,211,238,0.45)",
        modal: "0 24px 64px -24px rgba(0,0,0,0.85)",
      },
      animation: {
        "bounce-slow": "bounce 1.2s infinite",
        "fade-in": "fadeIn 0.25s ease-out both",
        "rise-in": "riseIn 0.35s cubic-bezier(0.21,0.85,0.36,1) both",
        "float-slow": "floatY 7s ease-in-out infinite",
        "float-slower": "floatY 11s ease-in-out infinite",
        "spin-slow": "spin 14s linear infinite",
        "pulse-soft": "pulseSoft 2.4s ease-in-out infinite",
        shimmer: "shimmer 2.2s linear infinite",
      },
      keyframes: {
        fadeIn: {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        riseIn: {
          from: { opacity: "0", transform: "translateY(10px) scale(0.985)" },
          to: { opacity: "1", transform: "translateY(0) scale(1)" },
        },
        floatY: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-14px)" },
        },
        pulseSoft: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.45" },
        },
        shimmer: {
          from: { backgroundPosition: "200% 0" },
          to: { backgroundPosition: "-200% 0" },
        },
      },
    },
  },
  plugins: [],
};
