// Website build settings. The site address comes from config/app.env like every other URL.
import path from "node:path";
import preact from "@astrojs/preact";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "astro/config";
import dotenv from "dotenv";

const repoRoot = path.resolve(process.env.DIGEST_ROOT ?? path.join(process.cwd(), "..", ".."));
dotenv.config({ path: path.join(repoRoot, ".env"), quiet: true });
dotenv.config({ path: path.join(repoRoot, "config", "app.env"), quiet: true });

export default defineConfig({
  site: process.env.SITE_URL,
  base: process.env.SITE_BASE_PATH,
  trailingSlash: "ignore",
  integrations: [preact()],
  vite: {
    plugins: [tailwindcss()],
    // The pages read ../../data, ../../config and ../../docs at build time.
    server: { fs: { allow: [repoRoot] } },
  },
});
