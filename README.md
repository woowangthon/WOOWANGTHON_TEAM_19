# AI 멘토 안드로이드 APK 빌드 소스 (TWA)

`https://chingu1.vercel.app` 웹앱을 크롬 엔진으로 감싼 Trusted Web Activity 프로젝트(Bubblewrap 생성 + Gradle).
배포된 APK는 저장소 Release `v1.0-apk`. 서명 키·비밀번호는 이 브랜치에 없다(저장소 밖에 보관).

- 패키지 `app.vercel.chingu1`, minSdk 24, targetSdk 36
- 빌드: `./gradlew assembleRelease`(JDK 17) → `zipalign` → `apksigner sign`
- 주소창 없이 열리려면 운영 `/.well-known/assetlinks.json`의 지문이 서명 키와 같아야 한다(main의 `frontend/public/.well-known/assetlinks.json`).
