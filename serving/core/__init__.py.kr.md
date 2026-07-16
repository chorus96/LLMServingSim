# `serving/core/__init__.py` 분석

`serving.core` 하위 패키지의 마커 모듈입니다. docstring만 담고 있으며 실행 코드는
없습니다.

## 개요

| 항목 | 내용 |
| --- | --- |
| 역할 | 하위 패키지 마커 + 임포트 규약 안내 |
| 임포트 규약 | 내부는 상대(`from .X import ...`), 외부는 `from serving.core.X import ...` |

## 블록 다이어그램

```mermaid
flowchart LR
    MAIN["serving.__main__<br/>(반복 루프)"] --> CORE["serving.core<br/>각 모듈이 루프의 한 조각을 소유"]
```

## 참고

- 각 core 모듈은 `serving.__main__`이 구동하는 반복 루프의 한 부분을 담당합니다.
