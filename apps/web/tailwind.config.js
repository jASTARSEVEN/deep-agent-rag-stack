/** 前端骨架使用的 Tailwind 設定。 */

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#122117",
        moss: "#355c44",
        sand: "#efe8da",
        ember: "#a95b3c",
      },
    },
  },
  plugins: [],
};
