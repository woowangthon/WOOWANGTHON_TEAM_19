# 디자인 ↔ 코드 연결표 (GPT/디자이너용)

코드는 이미 화면 흐름이 돌아갑니다. 디자인은 아래 세 곳만 바꾸면 반영됩니다.

| 바꿀 것 | 파일 | 방법 |
|---|---|---|
| 색·글자 크기·모서리·간격 | `src/styles/tokens.css` | 변수 **이름은 그대로**, 값만 변경 |
| 캐릭터 그림 | `public/mascot/*.png` | 같은 파일명으로 교체 (256×256, 투명 배경) |
| 컴포넌트 모양(버튼·카드·칩·말풍선·키패드·탭) | `src/styles/global.css` | 클래스 이름 유지, 속성만 변경 |

## 캐릭터 표정 파일 (6개)
| 파일 | 쓰는 곳 |
|---|---|
| wave.png | 오늘 시작, 수다, 역할 선택 |
| think.png | 같이 풀기(힌트), 짚어주는 스타일 |
| cheer.png | 학습 완료, 정답, 같이 풀어주는 스타일 |
| promise.png | 약속 (손가락 들기) |
| calm.png | 오답 "괜찮아", 위기 화면, 들어주는 스타일 |
| read.png | 마무리 (요약 카드 들기) |

## 토큰 목록
`--color-bg, --color-surface, --color-surface-muted, --color-primary, --color-primary-strong, --color-primary-soft, --color-accent, --color-accent-soft, --color-text, --color-text-muted, --color-border, --color-danger, --color-danger-soft, --adult-primary, --adult-primary-strong, --adult-primary-soft, --font-family, --font-size-caption/body/title/hero/keypad, --space-1~5, --radius-sm/md/lg/pill, --button-shadow, --frame-width, --frame-height`
