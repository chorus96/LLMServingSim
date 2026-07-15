# LLMServingSim 문서 사이트 (`docs/`)

https://llmservingsim.ai 의 LLMServingSim 문서 사이트를 갱신하는
협업자(사람 및 AI 코딩 에이전트)를 위한 가이드라인입니다.

저장소의 `README.md`는 의도적으로 최소한이며, 설치 + 실행을 넘어서는 모든 것에
대해 독자를 여기로 안내합니다. 장문 콘텐츠(CLI 플래그 표, 데이터셋 스키마,
프로파일러 설명, 검증 결과)는 README가 아니라 이 사이트에 있습니다. README와 docs
분리는 루트 `AGENTS.md`를 참고하세요.

## 이것은 무엇인가

공개 LLMServingSim 문서를 제공하는 [Docusaurus 3](https://docusaurus.io/)
사이트(TypeScript, classic preset)입니다. 사이트는 두 개의 최상위 navbar 섹션으로
나뉩니다:

- **For Users** — 설치, 시뮬레이터/프로파일러/bench 가이드, 설정 레퍼런스. (현재
  유일하게 채워진 섹션.)
- **For Contributors** — LLMServingSim 자체를 개발하는 사람들을 위한 온보딩. 현
  단계에서는 자리 표시자만.

참조 디자인은 [vLLM 문서](https://docs.vllm.ai/en/latest/)입니다 — 사이드바 우선
내비게이션, 깊은 계층, 대상 세분화.

## 로컬 개발

요구 사항: **Node.js ≥ 20**(사이트는 Node 18 지원을 중단한 Docusaurus 3를 사용)와
**pnpm**.

```bash
cd docs/
pnpm install
pnpm start          # http://localhost:3000 의 개발 서버
pnpm build          # docs/build/로의 정적 빌드
pnpm serve          # 프로덕션 빌드를 로컬에서 서빙
```

PR을 보내기 전에 최소 한 번은 `pnpm build`를 실행하세요 — 개발 서버는 프로덕션
빌드보다 관대합니다(깨진 링크, 죽은 앵커 등은 빌드를 실패시킴).

## 저장소 레이아웃

```
docs/
├── docusaurus.config.ts        사이트 메타데이터, navbar, footer, theme
├── sidebars.ts                 사이드바 트리 (userSidebar, contributorSidebar)
├── docs/                       markdown 콘텐츠 (최상위 섹션당 폴더 하나)
│   ├── getting-started/
│   ├── simulator/
│   ├── profiler/
│   ├── bench/
│   ├── validation/
│   ├── workloads/
│   ├── reference/
│   └── contributor/
├── src/
│   ├── pages/index.tsx         랜딩 페이지 (Hero + feature 카드)
│   ├── pages/index.module.css  랜딩 페이지 스타일
│   ├── components/
│   │   └── HomepageFeatures/   랜딩 페이지의 네 개 feature 카드
│   └── css/custom.css          전역 theme 오버라이드 (primary color 등)
└── static/
    ├── CNAME                   커스텀 도메인 (llmservingsim.ai)
    └── img/                    favicon, logo, social card
        ├── llmservingsim_full_primary_transparent.png       light-mode 로고 (indigo + black)
        ├── llmservingsim_full_primary_dark_transparent.png  dark-mode 로고 (indigo + white)
        ├── llmservingsim_full_reverse_white_transparent.png 전체 흰색 reverse
        ├── llmservingsim_full_mono_black_transparent.png    전체 검정 mono
        └── llmservingsim_compact_primary_transparent.png    navbar/compact 마크
```

dark-mode 로고는 루트 `README.md`에서 `<picture>` + `prefers-color-scheme`를 통해
참조됩니다; light 변형은 웹사이트의 hero/navbar 기본값이며 dark 모드에서는 CSS
`invert(1) hue-rotate(180deg)` 필터를 적용합니다.

## 새 문서 페이지 추가

1. `docs/` 아래의 섹션 폴더를 선택(또는 새로 생성, 아래 참고).
2. markdown 파일을 생성:

   ```markdown
   ---
   sidebar_position: 3
   title: Reading the Output
   ---

   # Reading the Output

   ...내용...
   ```

   `sidebar_position`은 섹션 내 순서를 제어합니다. `title`은 사이드바 라벨을
   제어합니다(생략 시 H1이 기본값).

3. 페이지가 관련 사이드바에 자동으로 나타납니다 — 사이드바는 폴더 구조에서 자동
   생성됩니다(`sidebars.ts` 참고).

## 새 섹션(최상위 폴더) 추가

1. 폴더를 생성, 예: `docs/new-section/`.
2. `_category_.json`을 추가:

   ```json
   {
     "label": "New Section",
     "position": 8,
     "link": {
       "type": "generated-index",
       "description": "What this section is about."
     }
   }
   ```

3. `sidebars.ts`의 `userSidebar` 또는 `contributorSidebar` 아래에 섹션을 추가.

## 랜딩 페이지 편집

- **Hero**(제목, 태그라인, 버튼): `src/pages/index.tsx`
- **Feature 카드**(hero 아래의 네 개 아이콘 + 텍스트):
  `src/components/HomepageFeatures/index.tsx` — `FeatureList` 배열을 편집.
- **Hero / 카드 스타일**: `src/pages/index.module.css`와
  `src/components/HomepageFeatures/styles.module.css`.
- **전역 색상 / 폰트**: `src/css/custom.css`.

## navbar / footer / 메타데이터 편집

`docusaurus.config.ts`:

- `title`, `tagline`, `url`, `favicon` — 최상위 사이트 메타데이터
- `themeConfig.navbar.items` — nav 링크(사이드바 링크는 `type: 'docSidebar'` 사용)
- `themeConfig.footer.links` — footer 열
- `presets[0][1].docs.editUrl` — "Edit this page" 링크 대상

## 배포

사이트는 `docs/**`를 건드리는 `main`으로의 모든 push에서 GitHub Actions를 통해
자동 배포됩니다:

1. Action이 저장소를 체크아웃하고 Node 22 + pnpm을 설치.
2. `docs/`에서 `pnpm install --frozen-lockfile && pnpm build`를 실행.
3. `actions/upload-pages-artifact@v3`를 통해 `docs/build/`를 Pages artifact로 업로드.
4. `actions/deploy-pages@v4`가 artifact를 GitHub Pages에 게시(저장소 Settings →
   Pages → Source = **GitHub Actions**). 커스텀 도메인 `llmservingsim.ai`는
   `docs/static/CNAME`로 보존됨.

성공적인 배포는 보통 병합 후 ~2분이 걸립니다. 빌드가 실패하면 이전 배포가 그대로
유지됩니다.

Pages-source 토글(`GitHub Actions` vs `Deploy from a branch`)은 일회성 저장소 설정
선택입니다; source가 다른 것으로 설정되면 워크플로우는 실행되지만 배포 단계는
조용히 no-op이 됩니다.

## 규약

- **언어**: 영어만. LLMServingSim 저장소의 나머지와 일치.
- **코드 블록**: 항상 언어를 지정(` ```bash `, ` ```python `, ` ```yaml `).
  사이트의 Prism 설정은 bash, python, json, yaml을 사전 로드.
- **이미지**: `static/img/` 아래에 두고 `/img/<file>.png`로 참조.
- **내부 링크**: 전체 URL이 아니라 `/docs/simulator/cli-overview` 같은 상대 경로
  사용. `onBrokenLinks: 'throw'`가 죽은 링크에서 빌드를 실패시킴.
- **컴포넌트 이름**: PascalCase(`HomepageFeatures`).
- **파일 이름**: 문서는 `kebab-case.md`, URL slug와 일치.

## 아직 명시적으로 범위에 **없는** 것

이들은 사이트에 콘텐츠와 추진력이 더 생길 때까지 연기됩니다:

- 모든 문서 페이지의 완전한 콘텐츠(대부분 stub)
- Algolia DocSearch 통합
- 버전 관리 문서(latest vs v1.x.y)
- 국제화
- 버전 관리 changelog 페이지(footer "Changelog"는 여전히 GitHub으로 연결)
- 블로그
- Python 소스에서의 API 레퍼런스 자동 생성

## 참조 사이트

레이아웃이나 톤에 대해 의심스러우면 vLLM 문서를 보세요:
[https://docs.vllm.ai/en/latest/](https://docs.vllm.ai/en/latest/).
