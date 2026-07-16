# `profiler/v0/profiler/layers/__init__.py` 분석

**레거시 v0 레이어 프로파일 서브패키지 마커**입니다(빈 파일). 비-어텐션
레이어(qkv/o/MLP/norm 등) 프로파일러(`main.py`)를 담습니다.

## 개요

| 항목 | 내용 |
| --- | --- |
| 역할 | `profiler.v0.profiler.layers` 패키지 선언(빈 파일) |
| 하위 | main.py(비-어텐션 레이어 프로파일러) |

## 블록 다이어그램

```mermaid
flowchart LR
    INIT["layers/__init__.py"] --> M["main.py"]
```

## 참고

- v0 레거시 코드로 참조용으로만 유지됩니다.
