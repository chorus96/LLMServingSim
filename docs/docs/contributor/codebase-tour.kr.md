---
sidebar_position: 3
title: 코드베이스 둘러보기
---

# 코드베이스 둘러보기

이 페이지는 "X를 추가하거나 변경하고 싶은데, 어디를 건드리나?"에 답합니다. 이는 동작
레퍼런스가 아니라 디렉터리 맵입니다. 각 부분이 *무엇을* 하는지는
**[시뮬레이터](/docs/simulator/architecture)**와 **[프로파일러](/docs/profiler/overview)**
섹션을 참고하세요.

## 다섯 영역

```
LLMServingSim/
├── serving/      시뮬레이터     Python, 핵심 루프
├── profiler/     프로파일러     Python, vLLM 기반 지연 캡처
├── bench/        Bench          Python, 실제 vLLM 실행 + sim 검증
├── workloads/    워크로드       JSONL 트레이스 + 생성기
├── configs/      설정           JSON: cluster / model / PIM
├── scripts/      환경 스크립트  Docker 실행기 + 빌더
└── astra-sim/    백엔드         C++ analytical 네트워크 시뮬레이터
```

각 영역은 명확한 경계를 가집니다. **일반적인 PR은 이들 중 하나나 둘을 건드리지, 전부가
아닙니다.** 단일 변경을 위해 네 영역을 편집하고 있다면, 멈추고 범위를 재고하세요.

## 시뮬레이터 (`serving/`)

대부분의 기여자 작업이 일어나는 곳.

```
serving/
├── __main__.py              CLI + 메인 루프
└── core/
    ├── scheduler.py         vLLM 스타일 continuous batching
    ├── trace_generator.py   프로파일 조회 -> 텍스트 트레이스
    ├── memory_model.py      KV / 가중치 / CXL 바이트 회계
    ├── graph_generator.py   텍스트 트레이스 -> Chakra protobuf
    ├── controller.py        ASTRA-Sim 서브프로세스 IPC
    ├── router.py            인스턴스 간 요청 라우팅
    ├── gate_function.py     MoE expert 라우팅
    ├── config_builder.py    클러스터 설정 -> ASTRA-Sim 입력
    ├── power_model.py       전력 / 에너지 추정
    ├── pim_model.py         PIM 장치 모델
    ├── request.py           Request / Batch dataclass
    ├── radix_tree.py        Prefix cache (RadixCache, SGLang에서)
    ├── logger.py            Rich 기반 로깅 + stdio 캡처
    └── utils.py             모델 설정 로딩, 포매터
```

**의도별로 건드릴 곳:**

| 의도 | 편집 |
| --- | --- |
| 스케줄링 정책 변경 | `scheduler.py` |
| 지연 조회 방법 변경 | `trace_generator.py`(`_lookup_*`) |
| 바이트 회계 변경(KV, 가중치, prefix cache) | `memory_model.py` |
| 인스턴스 간 라우팅 변경 | `router.py` |
| 새 CLI 플래그 추가 | `__main__.py`(argparse), 그다음 전달 |
| MoE expert 분배 변경 | `gate_function.py` |
| ASTRA-Sim 입력 생성 변경 | `config_builder.py` |
| 새 전력 구성 요소 추가 | `power_model.py` |

## 프로파일러 (`profiler/`)

```
profiler/
├── __main__.py              CLI 디스패치 (profile / slice)
├── core/                    내부 구현 (runner, engine, categories, fit_alpha)
├── models/<model_type>.yaml 아키텍처 카탈로그 (HF model_type당 하나)
├── perf/<hw>/<model>/...    출력 번들 (카테고리별 CSV)
└── profile.sh               편집 가능한 사용자 템플릿
```

**의도별로 건드릴 곳:**

| 의도 | 편집 |
| --- | --- |
| 새 하드웨어 타깃 추가 | `HARDWARE=`를 설정하고 프로파일러 실행; 출력이 `perf/<hw>/`에 착지. **[프로파일러 / 하드웨어 추가](/docs/profiler/adding-hardware)** 참고 |
| 새 모델 아키텍처 추가 | `profiler/models/<model_type>.yaml`에 YAML 넣기. **[프로파일러 / 모델 아키텍처 추가](/docs/profiler/adding-model-architecture)** 참고 |
| skew alpha 피팅 변경 | `core/fit_alpha.py` |
| 어떤 카테고리가 프로파일되는지 변경 | `core/categories.py` + `core/runner.py` |
| 출력 CSV 열 변경 | `core/writer.py`(그리고 그것을 소비하는 `serving/core/trace_generator.py`의 `_load_perf_db()`) |

## Bench (`bench/`)

```
bench/
├── __main__.py              CLI (run / validate)
├── core/                    AsyncLLM 드라이버, recorder, validator
├── examples/<model>/        커밋된 end-to-end 실행
└── results/<run_id>/        임시 실행의 출력
```

검증 방법론 자체(vLLM이 어떻게 구동되는지, 어떤 지표가 비교되는지, 어떤 플롯이
방출되는지)를 변경하는 경우에만 이것을 건드립니다. 일상적 "내 변경이 회귀했나?" 용도는
**[변경 사항 검증](./validating-changes)**을 참고하세요.

## 설정 (`configs/`)

```
configs/
├── cluster/<name>.json      클러스터 토폴로지 (주된 것)
├── model/<org>/<name>.json  모델 아키텍처 (HF config.json의 부분집합)
└── pim/<name>.ini           PIM 장치 스펙 (DRAMSim3 형식)
```

클러스터 설정은 `serving/` 밖에서 가장 많이 편집되는 파일입니다. 새 시나리오를 추가하는
것은 거의 항상 새 `configs/cluster/<scenario>.json`을 넣고 시뮬레이터 코드를 전혀 건드리지
않는 것을 의미합니다. 필드별 스키마는 **[레퍼런스 / 클러스터
설정](/docs/reference/cluster-config)**에 있습니다.

## 워크로드 (`workloads/`)

```
workloads/
├── *.jsonl                  데이터셋 (줄당 하나의 요청 또는 세션)
├── generators/              ShareGPT / SWE-bench JSONL 빌더
└── README.md                JSONL 형식 레퍼런스
```

새 워크로드 생성기 추가는 격리된 변경입니다: `generators/` 아래의 새 모듈,
`python -m workloads.generators.<your_module>`로 실행 가능. 기존 패턴은 **[워크로드 /
ShareGPT 생성기](/docs/workloads/sharegpt-generators)**를 참고하세요.

## ASTRA-Sim (`astra-sim/`)

C++ 네트워크 시뮬레이터, 서브모듈로 존재. **변경이 시뮬레이터 통합을 대상으로 하지 않는
한 편집하지 마세요.** 대부분의 시뮬레이터 측 변경은 이것을 결코 건드리지 않습니다.

편집할 수 있는 몇 안 되는 파일:

| 파일 | 이유 |
| --- | --- |
| `astra-sim/extern/graph_frontend/chakra/src/converter/llm_converter.py` | 새 트레이스 `comm_type` 문법, 새 메모리 위치 enum |
| `astra-sim/astra-sim/system/Workload.cc` | 커스텀 collective 발행, `involved_dim` 처리 |
| `astra-sim/astra-sim/system/AstraMemoryAPI.hh` | 새 메모리 계층 enum(`llm_converter.py`와 짝) |
| `astra-sim/inputs/...` | 편집하지 마세요. 매 실행마다 `config_builder.py`가 생성 |

ASTRA-Sim을 편집한다면, 테스트 전에 `./scripts/compile.sh`를 재실행하세요.

## 스크립트 (`scripts/`)

```
scripts/
├── docker-sim.sh            Sim 컨테이너 실행기
├── docker-vllm.sh           vLLM 컨테이너 실행기 (프로파일러 / bench)
├── install-vllm.sh          베어메탈 vLLM 설치 (uv venv)
└── compile.sh               ASTRA-Sim + Chakra 빌드
```

이것들은 드물게 건드립니다. 새 진입점을 추가한다면, 더 많은 셸 스크립트를 추가하기보다
`python -m <module>`(기존 컨테이너 내에서 처리됨)을 선호하세요.

## 테스트와 fixture

**단위 테스트 스위트가 없습니다.** 검증은 다음으로 이루어집니다:

1. smoke `python -m serving …`를 실행하고 출력 CSV를 검사.
2. 알려진 양호한 vLLM 재실행에 대해 `python -m bench validate` 실행(**[변경 사항
   검증](./validating-changes)** 참고).

깔끔한 입력과 출력을 가진 기능(새 `_lookup_*` 함수, 새 메모리 회계 헬퍼)을 추가할 때,
`scripts/` 아래에 스크립트나 브랜치에 체크인된 노트북을 자유롭게 추가하세요. 프로젝트는
아직 공식 테스트 프레임워크를 채택하지 않았습니다; 그 자체가 열린 기여 기회입니다.

## 문서가 있는 곳

| 대상 | 위치 |
| --- | --- |
| 사용자용 문서(이 사이트) | `docs/` |
| 모듈별 개발자 노트 | `<module>/README.md`(각 최상위 Python 모듈이 하나를 가짐) |
| 최상위 프로젝트 README | `README.md` |
| AI 에이전트를 위한 프로젝트 맥락 | `CLAUDE.md`(`AGENTS.md`를 반영) |

동작을 변경할 때, `docs/` 아래 관련 페이지를 업데이트하세요. 기능을 추가할 때, 웹사이트가
다루지 않는 것을 다룬다면 모듈 자체의 `README.md`도 업데이트하세요.

## 다음 단계

- **[코딩 규약](./conventions)**: 모든 PR이 따르는 규칙.
- **[변경 사항 검증](./validating-changes)**: 변경이 동작함을 증명하는 방법.
