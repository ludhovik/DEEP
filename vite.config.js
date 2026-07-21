import { defineConfig } from "vite";

export default defineConfig({
  server: {
    host: "127.0.0.1",
    // Enables /@fs/<absolute-path> for paths entered in the Dataset text box.
    // The development server remains bound to localhost.
    fs: {
      strict: false,
    },
  },
  preview: {
    host: "127.0.0.1",
  },
});
