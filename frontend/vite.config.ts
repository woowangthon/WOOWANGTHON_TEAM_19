import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// 개발 서버: npm run dev → http://localhost:5173
// 백엔드(FastAPI)와 붙일 때는 .env에 VITE_API_MODE=http, VITE_API_BASE=http://localhost:8000 을 넣는다.
export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 5173 },
});
