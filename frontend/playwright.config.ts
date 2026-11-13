import { defineConfig } from "@playwright/test";

// Mobile smoke test against a running app: BASE_URL (default http://localhost:3000) with the API behind it.
export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  use: { baseURL: process.env.BASE_URL || "http://localhost:3000", viewport: { width: 390, height: 844 },
         deviceScaleFactor: 2, isMobile: true, hasTouch: true },
  projects: [
    { name: "light-390", use: { colorScheme: "light" } },
    { name: "dark-390", use: { colorScheme: "dark" } },
    { name: "light-360", use: { colorScheme: "light", viewport: { width: 360, height: 780 } } },
  ],
});
