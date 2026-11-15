import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles/global.css';

// ?frame=phone: 넓은 화면에서도 휴대폰 모형(360×640)으로 보기(시연 영상 촬영용). global.css 「휴대폰·태블릿·PC 틀」
if (new URLSearchParams(location.search).get('frame') === 'phone') document.documentElement.dataset.frame = 'phone';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
