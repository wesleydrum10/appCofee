module.exports = {
  content: ["./templates/**/*.html", "./*/templates/**/*.html", "./static/js/**/*.js", "./*/forms.py"],
  theme: {
    extend: {
      colors: {
        cream: "#fcf9f4",
        alabaster: "#fdfbf7",
        latte: "#e8dec8",
        butter: "#f4ece1",
        espresso: "#2b1e1a",
        cocoa: "#482d25",
        caramel: "#c88242",
        honey: "#d99557",
        mocha: "#4a3c38",
        dust: "#7c6c67",
        sage: "#3d7b54",
        terracotta: "#b84a39"
      },
      fontFamily: {
        display: ["Playfair Display", "serif"],
        sans: ["Plus Jakarta Sans", "system-ui", "sans-serif"]
      },
      boxShadow: {
        warm: "0 2px 8px -2px rgba(43, 30, 26, 0.04)",
        float: "0 4px 16px -4px rgba(43, 30, 26, 0.08)",
        dock: "0 -4px 24px -4px rgba(43, 30, 26, 0.09)"
      }
    }
  }
};
