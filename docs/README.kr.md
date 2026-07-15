# Website

이 웹사이트는 최신 정적 웹사이트 생성기인 [Docusaurus](https://docusaurus.io/)로 빌드됩니다.

## 설치

```bash
yarn
```

## 로컬 개발

```bash
yarn start
```

이 명령은 로컬 개발 서버를 시작하고 브라우저 창을 엽니다. 대부분의 변경 사항은 서버를 재시작하지 않아도 실시간으로 반영됩니다.

## 빌드

```bash
yarn build
```

이 명령은 정적 콘텐츠를 `build` 디렉터리에 생성하며, 어떤 정적 콘텐츠 호스팅 서비스로도 서빙할 수 있습니다.

## 배포

SSH 사용:

```bash
USE_SSH=true yarn deploy
```

SSH 미사용:

```bash
GIT_USER=<GitHub 사용자명> yarn deploy
```

GitHub Pages로 호스팅하는 경우, 이 명령은 웹사이트를 빌드하고 `gh-pages` 브랜치에 푸시하는 편리한 방법입니다.
