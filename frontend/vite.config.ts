import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { listCosmeticArt } from './scripts/cosmetic-art.mjs';

// 개발 서버: npm run dev → http://localhost:5173
// 백엔드(FastAPI)와 붙일 때는 .env에 VITE_API_MODE=http, VITE_API_BASE=http://localhost:8000 을 넣는다.
export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 5173 },
  // 꾸미기 그림 목록 = public/mascot 안 실제 파일(빌드 때 읽음, 명세 4.12 5-2-1)
  define: { __COSMETIC_ART__: JSON.stringify(listCosmeticArt(new URL('./public/mascot/', import.meta.url))) },
});
