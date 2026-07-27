/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{html,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          black: "#050000",
          accent: "#49fce2",
          amber: "#eb881e",
          warning: "#910303",
        },
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
