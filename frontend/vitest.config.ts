import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    coverage: {
      include: [
        "src/components/ui/StatusBadge.tsx",
        "src/services/apiClient.ts",
        "src/utils/format.ts",
      ],
      provider: "v8",
      reporter: ["text", "html"],
      thresholds: {
        branches: 70,
        functions: 75,
        lines: 75,
        statements: 75,
      },
    },
    environment: "jsdom",
    environmentOptions: {
      jsdom: {
        url: "http://127.0.0.1:5173",
      },
    },
    setupFiles: ["./src/test/setup.ts"],
  },
});
