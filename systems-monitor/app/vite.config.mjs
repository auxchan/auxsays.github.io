import { defineConfig } from "vite";

export default defineConfig({
  base: "/systems-monitor/",
  build: {
    outDir: "../.build/ui",
    emptyOutDir: true,
    manifest: true,
    sourcemap: false,
    rollupOptions: {
      input: "src/main.tsx",
      output: {
        entryFileNames: "assets/[name]-[hash].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]"
      }
    }
  }
});
