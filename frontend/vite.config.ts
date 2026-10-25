import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// dev: the FastAPI backend runs on :8000 (uv run studio); production: the backend serves dist/
export default defineConfig({
  plugins: [react()],
  server: { port: 5180, proxy: { '/api': 'http://127.0.0.1:8000' } },
});
