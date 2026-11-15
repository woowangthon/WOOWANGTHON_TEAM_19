# LLM 공급자 약관 × 미성년 사용자 — 조사 노트 v0.1

- 작성일: 2026-11-08 (제출 11-15, 배포 11-10)
- 대상: 「친구1」 — 학원 초·중학생(10~15세)용 AI 멘토 웹앱. 백엔드가 LLM API를 호출하고, 아이는 LLM 서비스에 직접 가입하지 않음.
- 후보: OpenAI API / Anthropic Claude API / Google Gemini Developer API(AI Studio)
- 근거 원칙: 공급자 공식 페이지(openai.com·developers.openai.com / anthropic.com·claude.com / aistudio.google.com·policies.google.com)와 law.go.kr·korea.kr·msit.go.kr만 사용. 소비자 제품(ChatGPT·Claude.ai·Gemini 앱) 연령 제한은 제외했다.
- 이 문서는 법률 자문이 아니다. 확신도 "하"·"확인 필요" 항목은 제출 전 담당자가 원문을 다시 열어 확인한다.

---

## 1. 한 장 요약

1. **11-15 시연용 추천: Anthropic Claude API.** 세 곳 중 유일하게 "미성년자가 API 기반 제품과 직접 상호작용하는 것"을 명시적으로 허용하고 조건을 문서로 공개했다(Usage Policy + 지원 문서 '미성년자 대상 조직 가이드라인', 2026-03-16 갱신). 조건은 AI임을 매 세션 시작에 고지, 연령 확인·콘텐츠 필터·모니터링, 아동 개인정보법 준수 사실을 공개 페이지에 명시 — 모두 명세 v0.3 4.9에 이미 있거나 한 줄로 추가 가능하다.
2. **OpenAI API는 차선.** 서비스 계약이 "부모·법정대리인 동의 없이 미성년자가 사용하게 하는 것"을 금지하므로 동의가 있으면 가능하나, 공식 개발자 안내가 **13세 미만 개인정보는 Zero Data Retention을 먼저 적용하지 않고 보내지 말 것**을 요구한다. ZDR은 OpenAI 사전 승인이 필요해 11-15까지 확보 불가능하다(시연은 합성 데이터라 당장 위반은 아니지만, 실서비스 경로가 막힌다).
3. **Gemini Developer API(AI Studio)는 제외.** 약관이 "18세 미만을 향하거나 18세 미만이 접근할 가능성이 높은 API 클라이언트"에서의 사용을 금지한다(2026-03-23 발효). 아동용 앱 자체가 약관 위반이다. (Vertex AI는 별도 약관 — 미확인.)
4. **보존·학습:** Anthropic·OpenAI 모두 API 입력·출력을 기본적으로 학습에 쓰지 않고, 기본 보존은 30일(남용 감시 목적). Anthropic은 정책 위반으로 플래그된 대화를 최대 2년 보관하는 예외가 있다. ZDR은 양쪽 다 별도 승인·계약 사항이다. "무보관"은 주장하지 않는다.
5. **화면·제출물에 반드시 적을 문구 3개:**
   - (대화 시작 화면) "**친구1은 AI예요. 사람이 아니라 인공지능(생성형 AI)과 대화하고 있어요.**" — Anthropic 추가 가이드라인 + 인공지능기본법 제31조 제1항 사전 고지.
   - (프라이버시 한 장·보호자 안내) "**대화 내용은 AI 모델 학습에 쓰이지 않습니다. AI 공급자(Anthropic)는 남용 감시를 위해 최대 30일 보관 후 삭제하며, 정책 위반으로 자동 분류된 경우 최대 2년 보관될 수 있습니다. 서버는 미국에 있어 국외 이전 동의를 받습니다.**"
   - (가입·공개 페이지) "**만 14세 미만 학생은 법정대리인 동의를 휴대폰 본인인증으로 확인한 뒤 사용합니다(개인정보 보호법 제22조의2, 시행령 제17조의2 제1항 제3호). 아동 개인정보 보호 법규를 준수합니다.**" — Anthropic이 "준수 사실을 공개 문서에 명시"하라고 요구.

---

## 2. 비교표

| 공급자 | 최종 사용자 연령 조건 | 학습 사용 기본값 | 보존 일수 · ZDR | 출처 URL | 문서 갱신일 | 확신도 |
| --- | --- | --- | --- | --- | --- | --- |
| **OpenAI API** | 미성년 사용 가능하되 **부모·법정대리인 동의 필수**(서비스 계약 3.3(c)). 18세 미만 대상 서비스는 COPPA 등 아동 보호법 준수. **13세 미만 개인정보는 ZDR 선적용 없이는 처리 금지**(개발자 안내). | 학습에 쓰지 않음(기본). 명시적 옵트인 시에만 공유. | 남용 감시 로그 **최대 30일**. ZDR·Modified Abuse Monitoring은 **OpenAI 사전 승인 필요**. 이미지·파일 입력은 ZDR이어도 CSAM 스캔. | 서비스 계약: https://openai.com/policies/services-agreement/ · 데이터: https://developers.openai.com/api/docs/guides/your-data · 18세 미만 안내: https://developers.openai.com/api/docs/guides/safety-checks/under-18-api-guidance · 이용정책: https://openai.com/policies/usage-policies/ | 서비스 계약 2026-01-01 발효 · 이용정책 현행 2025-10-29, **차기판 2026-11-20 시행**(아동·청소년 보호 조치 명확화) · 데이터·18세 미만 안내 페이지: 날짜 없음 | 미성년 허용 조건: **상** / 13세 미만 ZDR 요건: **중**(안내 문서가 "should not" 표현) |
| **Anthropic Claude API** | **미성년자 직접 상호작용 허용**, 단 지원 문서의 추가 가이드라인 + 모든 관련 법 준수. 가이드라인: 연령 확인, 콘텐츠 필터, 모니터링·신고 경로, AI임을 매 세션 시작 시 고지, COPPA 등 준수 사실을 공개 페이지에 명시, 정기 감사. 보호자 동의는 Anthropic 문서가 직접 요구하지 않음(법 준수로 흡수). 미성년 = 18세 미만. | **학습에 쓰지 않음**(상업 약관 B절 "Customer Content로 모델 학습 불가"). | 기본 **30일 내 삭제**. 예외: 정책 위반 플래그 시 입력·출력 **최대 2년**, 분류 점수 7년. ZDR은 **별도 합의**. | AUP: https://www.anthropic.com/legal/aup · 미성년 가이드라인: https://support.claude.com/en/articles/9307344-responsible-use-of-anthropic-s-models-guidelines-for-organizations-serving-minors · 상업 약관: https://www.anthropic.com/legal/commercial-terms · 보존: https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data | AUP 페이지 표시 "Effective Nov 12, 2026"(차기판으로 보임, 아래 6절) · 미성년 가이드라인 2026-03-16 · 상업 약관 2025-06-17 · 보존 문서 2026-07-01 | **상** |
| **Google Gemini Developer API (AI Studio)** | **18세 미만을 향하거나 접근할 가능성이 높은 API 클라이언트에서 사용 금지.** 개발자도 18세 이상. → 아동용 앱 불가. | **무료(Unpaid): 학습·제품 개선에 사용 + 사람 검토.** 유료(Paid): 제품 개선에 쓰지 않음. | 남용 감시 로그 **55일**(이용정책 페이지). 유료 약관 본문은 "제한된 기간". ZDR 언급 없음. | 약관: https://aistudio.google.com/docs/terms (ai.google.dev/gemini-api/terms에서 리다이렉트) · 이용정책: https://aistudio.google.com/docs/usage-policies · 금지 사용 정책: https://policies.google.com/terms/generative-ai/use-policy | 약관 2026-03-23 발효 · 이용정책 날짜 없음 · 금지 사용 정책 2024-12-17 | **상**(두 번 독립 추출로 동일 문구 확인) |

---

## 3. 공급자별 근거

### 3.1 OpenAI

- **미성년 사용 조건(서비스 계약 3.3(c))**: 고객은 "부모 또는 법정대리인의 동의 없이 미성년자가 OpenAI 서비스를 사용하도록 허용하는 행위"를 해서는 안 된다. 효력 발생일 2026-01-01. — https://openai.com/policies/services-agreement/ (한국어판 /ko-KR/ 자동 전환)
- **최종 사용자 정의**: "최종 사용자에는 … 학생 … 이 포함될 수 있습니다" — 같은 문서 정의 절. 교육 서비스 최종 사용자를 전제한다.
- **18세 미만 대상 서비스 안내(개발자 문서)**: 적용 대상은 "serve minors (under 18 years old)"인 조직. 준수 법에 "including the Children's Online Privacy Protection Act (COPPA)". 핵심 문장: "You should not use OpenAI services to process any personal data of children under 13" … "without first implementing zero data retention in our API." 권장 조치로 "age assurance systems to ensure only intended users can access the product", 연령 적합 콘텐츠 필터, 모니터링·에스컬레이션. 페이지에 갱신일 없음. — https://developers.openai.com/api/docs/guides/safety-checks/under-18-api-guidance
- **이용정책(현행 2025-10-29)**: "청소년의 OpenAI 제품 및 서비스 이용: OpenAI 도구를 사용하여 18세 미만인 사람을 위험에 빠뜨려서는 안 됩니다." 금지 예: "연령에 부적합한 콘텐츠를 미성년자에게 노출", "미성년자에게 부적합한 성적 또는 폭력적 역할 행위". 변경 이력: "2026년 10월 21일 … 아동과 청소년을 위한 보호 조치 … 명확히 … 2026년 11월 20일부터 시행". — https://openai.com/policies/usage-policies/
- **학습·보존**: "data sent to the OpenAI API is not used to train or improve OpenAI models"(옵트인 제외). 남용 감시 로그는 "up to 30 days". ZDR은 "subject to prior approval by OpenAI and acceptance of additional requirements". 페이지 갱신일 없음. — https://developers.openai.com/api/docs/guides/your-data
- 참고(API 아님): 소비자 ChatGPT 약관은 13세 이상·18세 미만 보호자 허락. App Developer Terms(ChatGPT 앱)는 13세 미만 개인정보 전송을 금지 — 모두 API 정책과 별개이므로 본문에서 제외.

### 3.2 Anthropic

- **Usage Policy, Additional Use Case Guidelines**: "Products serving minors, including organizations providing minors with the ability to directly interact with products that incorporate our API(s), must comply with the additional guidelines outlined in our Support article and all applicable laws." (PDF p.16) — https://www.anthropic.com/legal/aup (PDF: https://assets.claude.com/88cf16e8b7d203be16d2c726bcd28a6ec7c7f5c8.pdf)
- 같은 문서: "We define a minor or child to be any individual under the age of 18 years old, regardless of jurisdiction." (p.6) / "All consumer-facing chatbots or AI agents that communicate directly with external users must disclose to users that they are interacting with AI" … "at a minimum at the beginning of each chat session or in the product interface." (p.16)
- 문서 표기 "Effective—Nov 12, 2026". 오늘(11-08) 기준 아직 발효 전이므로 차기판으로 보인다. 현행판 날짜는 확인 필요(6절).
- **미성년자 대상 조직 가이드라인(지원 문서, 2026-03-16 갱신)**: 권장 기술 조치 — 연령 확인, 콘텐츠 모더레이션·필터, 모니터링·신고, 교육 자료. "Anthropic may provide a child-safety system prompt". 법 준수 — "comply with all applicable child safety and data privacy regulations, such as COPPA"이며 그 준수 사실을 "clearly stated on the organization's website or similar public-facing documentation". AI 고지 의무. 정기 감사, 위반율 높고 권고 미이행 시 계정 정지·해지 가능. 보호자 동의·13세 미만 별도 규정 없음. — https://support.claude.com/en/articles/9307344-responsible-use-of-anthropic-s-models-guidelines-for-organizations-serving-minors
- **학습**: 상업 약관 B절 "Anthropic may not train models on Customer Content from Services." Customer Content = Inputs + Outputs. 약관 발효 2025-06-17. "Services under these Terms are not for consumer use." — https://www.anthropic.com/legal/commercial-terms
- **보존**: API 입력·출력은 "within 30 days of receipt or generation" 삭제. 예외: "up to 2 years and trust and safety classification scores for up to 7 years if your chat is flagged". ZDR은 "agreed otherwise" 예외(별도 합의). 문서 갱신 2026-07-01. — https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data

### 3.3 Google Gemini Developer API (AI Studio)

- **연령**: "You must be 18 years of age or older to use the APIs." 그리고 서비스를 API 클라이언트에서 쓰면 안 되는 경우로 "that is directed towards or is likely to be accessed by individuals under the age of 18." 약관 "Effective March 23, 2026". — https://aistudio.google.com/docs/terms
- **무료 서비스 데이터**: "Google uses the content you submit to the Services and any generated responses to provide, improve, and develop" … "human reviewers may read, annotate, and process your API input and output." 경고: "Do not submit sensitive, confidential, or personal information to the Unpaid Services."
- **유료 서비스 데이터**: "Google doesn't use your prompts or responses to improve our products" / "Google logs prompts and responses for a limited period of time". (Grounding with Google Search 사용 시 30일 저장.)
- **보존 일수**: 이용정책 페이지 "Google retains the following data for fifty-five (55) days" — 프롬프트·맥락·출력, 금지 사용 정책 위반 탐지 목적. "not used to train or fine-tune any AI/ML models besides those used specifically for policy enforcement." 날짜 없음. — https://aistudio.google.com/docs/usage-policies
- **생성형 AI 금지 사용 정책**: 아동 관련 조항은 "Relates to child sexual abuse or exploitation" 하나뿐. "Last Modified: December 17, 2024". — https://policies.google.com/terms/generative-ai/use-policy

---

## 4. 한국 법 접점

**개인정보 보호법.** 제22조의2 제1항: "개인정보처리자는 만 14세 미만 아동의 개인정보를 처리하기 위하여 … 동의를 받아야 할 때에는 그 법정대리인의 동의를 받아야 하며, 법정대리인이 동의하였는지를 확인하여야 한다." 제2항은 동의를 받기 위한 최소 정보(시행령 제17조의2 제2항: 법정대리인의 성명·연락처)를 아동에게서 직접 수집할 수 있게 하고, 제3항은 아동에게는 "이해하기 쉬운 양식과 명확하고 알기 쉬운 언어"로 고지하라고 한다. 시행령 제17조의2 제1항은 확인 방법 7가지를 열거하며 제3호가 "동의 내용을 게재한 인터넷 사이트에 법정대리인이 동의 여부를 표시하도록 하고 법정대리인의 휴대전화 본인인증 등을 통하여 본인 여부를 확인하는 방법"이다 — 명세 v0.3 4.9-2의 설계와 일치한다. (법률 제21445호, 시행령 제36671호, 모두 시행 2026-09-11. 출처: https://www.law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1029334761 , https://www.law.go.kr/LSW/lsInfoR.do?lsiSeq=289537&efYd=20260911&ancYnChk=0 ) **확신도 상.** 10~15세 사용자 중 14세 미만만 법정대리인 동의 대상이고, 14·15세는 본인 동의로 족하나 쉬운 언어 고지는 동일하게 적용하는 편이 안전하다(이 마지막 문장은 설계 판단).

**인공지능기본법(인공지능 발전과 신뢰 기반 조성 등에 관한 기본법).** 법률 제21311호(2026-01-20 일부개정), law.go.kr 표시 시행일은 조문에 따라 2026-01-22와 2026-07-21이 함께 보인다(6절). 제2조 제5호 "생성형 인공지능"은 "글, 소리, 그림, 영상 … 결과물을 생성하는 인공지능시스템", 제7호 나목 "인공지능이용사업자: 가목의 사업자가 제공한 인공지능을 이용하여 … 인공지능서비스를 제공하는 자" — 친구1 팀은 이에 해당한다. **제31조 제1항**: "인공지능사업자는 고영향 인공지능이나 생성형 인공지능을 이용한 제품 또는 서비스를 제공하려는 경우 … 해당 인공지능에 기반하여 운용된다는 사실을 이용자에게 사전에 고지하여야 한다." **제2항**: "생성형 인공지능 … 결과물이 생성형 인공지능에 의하여 생성되었다는 사실을 표시하여야 한다." → **생성형 AI 사전 고지·결과물 표시 의무는 친구1에 적용된다. 확신도 상**(조문 직접 확인; 표시 방법 세부는 시행령 제23조·투명성 확보 가이드라인 — 본문 미열람, 확인 필요). **고영향 인공지능**: 제2조 제4호는 "사람의 생명, 신체의 안전 및 기본권에 중대한 영향을 미치거나 위험을 초래할 우려가 있는" 시스템으로서 각 목 영역에서 활용되는 것이며, 교육 관련 목은 차목 "「교육기본법」 제9조제1항에 따른 유아교육ㆍ초등교육 및 중등교육에서의 학생 평가"뿐이다. 친구1은 학원(학교가 아님)에서 쓰는 학습 멘토링이고 성적·진급 등 공식 평가를 하지 않으며, 정부 설명도 "최종 의사결정에 사람이 개입하면 고영향AI 대상에서 제외"라고 한다(korea.kr 2026-01-21). → **고영향 AI에 해당하지 않을 가능성이 높음. 확신도 중**(「고영향 인공지능 판단 가이드라인」 PDF 원문 미열람; 과기정통부 확인 요청 창구 https://www.msit.go.kr/user/ais/requestAi.do 는 "자체적으로 … 먼저 검토하신 뒤에" 요청하라고 안내). 과태료는 "최소 1년 이상 규제를 유예"·계도기간 운영(korea.kr 2026-01-21, https://www.korea.kr/news/policyNewsView.do?newsId=148958380 ). 조문 출처: https://www.law.go.kr/LSW/lsSideInfoP.do?lsiSeq=282791&joNo=0002&joBrNo=00&docCls=jo&urlMode=lsScJoRltInfoR , https://www.law.go.kr/LSW//lsSideInfoP.do?lsiSeq=282791&joNo=0031&joBrNo=00&docCls=jo&urlMode=lsScJoRltInfoR

---

## 5. 설계에 미치는 영향 — 명세 v0.3에 넣을 문장 초안

### 4.9 「프라이버시 설계 한 장」 — 4항을 아래로 교체

> 4. **AI 공급자는 Anthropic(Claude API)이다.** 상업 약관상 입력·출력은 모델 학습에 쓰이지 않고(B절), 남용 감시를 위해 최대 30일 보관 후 삭제된다. 정책 위반으로 자동 분류된 대화는 최대 2년 보관될 수 있다. 무보관(ZDR)은 별도 계약 사항이라 주장하지 않는다. 서버는 국외(미국)에 있어 국외 이전은 따로 알리고 동의받는다. 출처: anthropic.com/legal/commercial-terms(2025-06-17), privacy.claude.com 보존 문서(2026-07-01).

### 4.9 — 11항 신설

> 11. **아이에게 AI임을 먼저 말한다.** 매 대화 세션 시작에 "친구1은 AI예요"를 아이 화면에 띄운다(Anthropic 미성년자 대상 가이드라인 + 인공지능기본법 제31조 제1항 사전 고지). 답변 말풍선에는 "AI가 만든 답"을 상시 표시한다(제31조 제2항). 서비스 소개 페이지에 "아동 개인정보 보호 법규(개인정보 보호법 제22조의2 등)를 준수합니다"를 적는다 — Anthropic이 공개 문서 명시를 요구한다.

### 4.10 「심사위원이 물을 것」 — 1행 교체 + 1행 추가

> | "어느 공급자이고 약관 어디에 있나?" | Anthropic Claude API. 미성년자 직접 상호작용은 Usage Policy '추가 사용 사례 가이드라인'에서 허용(지원 문서 9307344, 2026-03-16). 학습 불사용·30일 보존(위반 플래그 시 2년). OpenAI는 13세 미만 개인정보에 ZDR 승인을 요구해 차선, Gemini Developer API는 18세 미만 대상 앱 자체를 금지해 제외 | 조사 노트 LLM_약관_미성년_v0.1. 완료 11-08 |
> | "AI 기본법 고영향 AI 아닌가? 고지는?" | 고영향 아님으로 자체 판단(제2조 4호 차목은 학교 '학생 평가'; 친구1은 학원 멘토링, 평가 결정 없음, 사람 개입). 생성형 AI 사전 고지·표시 의무(제31조 1·2항)는 적용 → 세션 시작 고지 + 말풍선 표시로 이행 | 판단 가이드라인 PDF 대조 1회. 11-12까지(담당 미정) |

---

## 6. 확인 못 한 것

1. **Anthropic AUP 현행판 날짜.** 페이지·PDF 모두 "Effective Nov 12, 2026"만 표시(오늘 11-08 기준 차기판). 현행판의 미성년 조항이 동일한지 version history에서 확인 필요. 미성년 가이드라인 지원 문서(2026-03-16)는 현행이므로 결론은 바뀌지 않을 가능성이 높다.
2. **OpenAI 서비스 계약의 학습 금지 조항 원문.** 3.3(c)·발효일은 확인했으나 "고객 콘텐츠로 서비스 개발·개선 금지" 조항 문구는 페이지 추출이 중단돼 미확인. 공식 데이터 문서(developers.openai.com/…/your-data)로 대체 인용함.
3. **OpenAI 이용정책 차기판(2026-11-20 시행)**의 아동·청소년 조항 변경 내용 — 제출(11-15) 직후 시행. 원문 미열람.
4. **Google Vertex AI(Google Cloud) 약관**은 Developer API와 별개. 18세 미만 제한이 같은지 미확인(후보 밖이라 조사하지 않음).
5. **인공지능기본법 시행일 표기 불일치.** law.go.kr이 같은 법률번호(제21311호)에 대해 2026-01-22와 2026-07-21 두 시행일을 보여 준다 — 2026-01-20 일부개정으로 일부 조문의 시행이 7-21로 미뤄진 것으로 보이나 제31조가 어느 쪽인지 미확인. 정부 보도(korea.kr 2026-01-21)는 1-22 시행으로 설명.
6. **시행령 제23조(고지·표시 방법)와 「인공지능 투명성 확보 가이드라인」(2026-01-22 공개, 1-27 수정) 본문** — 텍스트 챗봇의 "결과물 표시" 구체 방식(말풍선 표시로 충분한지) 미확인. 첨부가 hwpx/PDF.
7. **「고영향 인공지능 판단 가이드라인」(최신 2026-04-29 수정) PDF 본문** — 교육 영역 해석·학원 포함 여부 미열람. nia.or.kr 게시판(cbIdx=99835&bcIdx=28987)에 첨부.
8. **Anthropic·OpenAI 개발자 계정 자체의 연령·조직 요건**(학생 2명 팀이 '조직 고객'으로 가입 가능한지)은 이 조사 범위 밖.
9. 개인정보 보호법 제22조의2·시행령 제17조의2는 2026-09-11 시행 버전을 확인함. 그 이전 버전과의 차이는 보지 않음.

---

### 작업 기록
- 열람 방법: WebFetch(공식 페이지), law.go.kr 조문 링크, Anthropic Usage Policy PDF 직접 열람, OpenAI 페이지는 WebFetch 403으로 브라우저 렌더링(ko-KR 자동 전환본)에서 추출.
- 2차 자료(블로그·커뮤니티)는 인용하지 않음.
