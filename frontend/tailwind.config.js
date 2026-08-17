/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#f5f7fb",
          card: "#ffffff",
          hover: "#f1f5f9",
          border: "#dce3ed",
          muted: "#eef2f7",
        },
        accent: {
          DEFAULT: "#2563eb",
          dim: "#1d4ed8",
          glow: "#1e40af",
          soft: "rgba(37, 99, 235, 0.08)",
        },
        status: {
          success: "#10b981",
          error: "#ef4444",
          warning: "#f59e0b",
          info: "#6366f1",
        },
      },
      borderRadius: {
        bento: "16px",
        "bento-sm": "12px",
        "bento-lg": "20px",
      },
      boxShadow: {
        bento: "0 1px 2px rgba(15,23,42,0.04), 0 6px 18px rgba(15,23,42,0.035)",
        "bento-hover": "0 2px 4px rgba(15,23,42,0.05), 0 12px 28px rgba(15,23,42,0.07)",
        glow: "0 8px 20px rgba(37,99,235,0.18)",
      },
      backgroundImage: {
        "grid-pattern": "linear-gradient(rgba(37,99,235,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(37,99,235,0.035) 1px, transparent 1px)",
      },
      backgroundSize: {
        grid: "24px 24px",
      },
      animation: {
        "pulse-slow": "pulse 3s ease-in-out infinite",
        "fade-in": "fadeIn 0.3s ease-out",
        "slide-up": "slideUp 0.3s ease-out",
      },
      keyframes: {
        fadeIn: {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        slideUp: {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
