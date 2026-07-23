/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{html,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          950: "#07111f",
          900: "#0b1728",
          850: "#101f34",
          800: "#14263d",
        },
      },
      boxShadow: {
        soft: "0 18px 50px rgba(7, 17, 31, 0.16)",
      },
    },
  },
  plugins: [],
};
