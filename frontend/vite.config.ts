import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "lodash/isEqualWith": "lodash/isEqualWith.js"
    }
  },
  server: {
    port: 5173
  },
  preview: {
    port: 4173
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/setupTests.ts",
    globals: true,
    coverage: {
      provider: "v8"
    }
  }
});
