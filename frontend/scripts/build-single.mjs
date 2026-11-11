// 실행되는 단일 HTML 만들기: npm run build:single
// 결과: release/AI-멘토.html (CSS·JS를 파일 안에 넣음) + release/mascot/ (캐릭터 그림)
// → 폴더째 전달하면 받은 사람이 AI-멘토.html을 더블클릭해서 바로 실행할 수 있다(설치·서버 불필요, 가짜 서버 내장).
// 원리: file://에서는 <script type="module" src="..."> 가 막히므로 JS를 HTML 안에 직접 넣는다.
import { execSync } from 'node:child_process';
import { cpSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const tmp = 'dist-single';
execSync(`npx vite build --base ./ --outDir ${tmp} --emptyOutDir`, { stdio: 'inherit' });
const assets = join(tmp, 'assets');
const js = readdirSync(assets).filter((f) => f.endsWith('.js')).map((f) => readFileSync(join(assets, f), 'utf8'));
const css = readdirSync(assets).filter((f) => f.endsWith('.css')).map((f) => readFileSync(join(assets, f), 'utf8'));
let html = readFileSync(join(tmp, 'index.html'), 'utf8')
  .replace(/<script type="module"[^>]*src="[^"]+"[^>]*><\/script>/g, '')
  .replace(/<link rel="stylesheet"[^>]*>/g, '');
const safeJs = js.join('\n').replace(/<\/script/gi, '<\\/script');
html = html.replace('</head>', `<style>${css.join('\n')}</style>\n</head>`)
  .replace('</body>', `<script type="module">${safeJs}</script>\n</body>`);
rmSync('release', { recursive: true, force: true });
mkdirSync('release', { recursive: true });
writeFileSync(join('release', 'AI-멘토.html'), html);
if (existsSync(join(tmp, 'mascot'))) cpSync(join(tmp, 'mascot'), join('release', 'mascot'), { recursive: true });
rmSync(tmp, { recursive: true, force: true });
console.log('✓ release/AI-멘토.html + release/mascot/ — 더블클릭으로 실행');
