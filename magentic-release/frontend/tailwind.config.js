/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    `./src/pages/**/*.{js,jsx,ts,tsx}`,
    `./src/components/**/*.{js,jsx,ts,tsx}`,
  ],
  theme: {
    extend: {
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'scale-in': {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.1s ease-out',
        'scale-in': 'scale-in 0.1s ease-out',
      },
      typography: {
        DEFAULT: {
          css: {
            maxWidth: "100ch",
          },
        },
      },
      transitionProperty: {
        height: "height",
        spacing: "margin, padding",
      },
      colors: {
        primary: "var(--color-bg-primary)",
        secondary: "var(--color-bg-secondary)",
        accent: "var(--color-bg-accent)",
        light: "var(--color-bg-light)",
        tertiary: "var(--color-bg-tertiary)",
        "blue-400": "var(--color-blue-400)",
        "blue-700": "var(--color-blue-700)",
        "blue-800": "var(--color-blue-800)",
        "blue-900": "var(--color-blue-900)",

        "magenta-400": "var(--color-magenta-400)",
        "magenta-700": "var(--color-magenta-700)",
        "magenta-800": "var(--color-magenta-900)",
        "magenta-900": "var(--color-magenta-800)",
        "magenta-1000": "var(--color-magenta-1000)",
        "gray-700": "var(--color-gray-700)",
        "gray-800": "var(--color-gray-800)",
      },
      textColor: {
        accent: "var(--color-text-accent)",
        primary: "var(--color-text-primary)",
        "primary-active": "var(--color-text-primary-active)",
        secondary: "var(--color-text-secondary)",
        message: "var(--color-text-message)",
        "blue-400": "var(--color-blue-400)",
        "blue-700": "var(--color-blue-700)",
        "blue-800": "var(--color-blue-800)",
        "blue-900": "var(--color-blue-900)",

        "magenta-400": "var(--color-magenta-400)",
        "magenta-700": "var(--color-magenta-700)",
        "magenta-800": "var(--color-magenta-800)",
        "magenta-900": "var(--color-magenta-900)",

        "gray-700": "var(--color-gray-700)",
        "gray-800": "var(--color-gray-800)",
      },
      borderColor: {
        accent: "var(--color-border-accent)",
        primary: "var(--color-border-primary)",
        secondary: "var(--color-border-secondary)",
        "blue-400": "var(--color-blue-400)",
        "blue-700": "var(--color-blue-700)",
        "blue-800": "var(--color-blue-800)",
        "blue-900": "var(--color-blue-900)",

        "magenta-400": "var(--color-magenta-400)",
        "magenta-700": "var(--color-magenta-700)",
        "magenta-800": "var(--color-magenta-800)",
        "magenta-900": "var(--color-magenta-900)",

        "gray-700": "var(--color-gray-700)",
        "gray-800": "var(--color-gray-800)",
      },
      ringColor: {
        accent: "var(--color-text-accent)",
        primary: "var(--color-text-primary)",
        secondary: "var(--color-text-secondary)",
        "blue-400": "var(--color-blue-400)",
        "blue-700": "var(--color-blue-700)",
        "blue-800": "var(--color-blue-800)",
        "magenta-400": "var(--color-magenta-400)",
        "magenta-700": "var(--color-magenta-700)",
        "magenta-800": "var(--color-magenta-800)",
        "magenta-900": "var(--color-magenta-900)",
        "gray-700": "var(--color-gray-700)",
        "gray-800": "var(--color-gray-800)",

      },
    },
  },
  plugins: [
    require("@tailwindcss/typography"),
    function ({ addBase, theme }) {
      addBase({
        ":root": {
          "--tw-bg-opacity": "1",
          "--tw-text-opacity": "1",
          "--tw-border-opacity": "1",
        },
      });
    },
  ],
};
