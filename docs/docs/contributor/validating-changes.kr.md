---
sidebar_position: 5
title: 변경 사항 검증
---

# 변경 사항 검증

프로젝트는 (아직) 단위 테스트 스위트를 제공하지 않습니다. 검증은 시뮬레이터를 알려진
시나리오에 대해 실행하고 결과를 비교하여 이루어집니다. 이 페이지는 PR을 열기 전에
실행해야 하는 세 가지 확인을 비용 증가 순으로 다룹니다.

## 1. Smoke 실행 (모든 PR, ~30초)

최소 기준: 가장 작은 번들 시나리오를 실행하고 여전히 오류 없이 끝나는지 확인합니다.

```bash
python -m serving \
    --cluster-config configs/cluster/single_node_single_instance.json \
    --dataset workloads/example_trace.jsonl \
    --output outputs/smoke.csv \
    --num-reqs 10
```

확인할 것:

- 종료 코드가 0.
- `outputs/smoke.csv`에 헤더 + 10행.
- 끝의 throughput 로그 라인이 0이 아닌 `prompt_t`와 `decode_t`를 보임.

변경이 `serving/`에 있으면, 이것이 최소한입니다. smoke 실행을 깨뜨리는 커밋을 푸시하지
마세요.

## 2. 표적 시나리오 (변경이 관련 기능을 건드릴 때)

편집을 그것을 사용하는 시나리오에 매핑하세요. 번들된 클러스터 설정이 주요 기능을
커버합니다:

| 건드린 것이... | 실행 시나리오 |
| --- | --- |
| `scheduler.py`(어떤 경로든) | `single_node_single_instance.json` |
| Prefix caching, RadixCache | `--enable-prefix-sharing`을 가진 `single_node_multi_instance.json` |
| KV cache, eviction, 메모리 모델 | `single_node_memory_instance.json` |
| 다중 인스턴스 라우팅 | `single_node_multi_instance.json` |
| 프리필 / 디코드 분리 | `single_node_pd_instance.json` |
| MoE, expert 병렬화 | `single_node_moe_single_instance.json` |
| DP+EP wave sync | `single_node_moe_dp_ep_instance.json` |
| CXL 배치 | `single_node_cxl_instance.json` |
| PIM offload | `single_node_pim_instance.json` |
| 전력 모델 | `single_node_power_instance.json` |
| 트레이스 생성기, 그래프 생성기 | 위의 어느 것이든 |

`serving/run.sh`가 이 모든 것을 위한 바로 실행 가능한 명령을 담고 있습니다. 관련된 것을
선택하고 여전히 타당한 출력을 생성하는지 확인하세요.

## 3. Bench 검증 (end-to-end 정확도에 영향을 주는 변경)

변경이 실제 vLLM 대비 시뮬레이터의 출력을 움직일 수 있으면(`scheduler.py`,
`trace_generator.py`, `memory_model.py`, 프로파일 조회, MoE 회계의 무엇이든), 커밋된
참조 실행에 대해 bench 검증을 실행하세요.

bench 모듈은 실제 vLLM 실행을 캡처한 뒤, 같은 데이터셋에 대한 시뮬레이터의 출력을
비교합니다:

```bash
# 1. 기존 예제의 sim 측 재실행
./bench/examples/run.sh Llama-3.1-8B

# 2. 커밋된 vLLM 참조와 비교
./bench/examples/validate.sh Llama-3.1-8B
```

출력이 `bench/examples/Llama-3.1-8B/validation/`에 착지합니다:

- `summary.txt`: TTFT / TPOT / throughput의 집계 오차.
- 몇 개의 PDF: 요청별 latency CDF, throughput 타임라인, running-waiting 곡선.

커밋된 참조 베이스라인은 TTFT, TPOT, throughput에 대해 3% 미만 오차를 목표로 합니다.
**~5%를 넘는 회귀는 blocker입니다.** 더 작은 움직임은 PR 설명에 설명이 필요합니다(예: "이는
과소 계수 버그를 수정함; 새 오차가 기존보다 ground truth에 더 가까움").

검증 방법론에 대한 더 깊은 세부 사항은
[`bench/README.md`](https://github.com/casys-kaist/LLMServingSim/blob/main/bench/README.md)를
참고하세요.

## 4. 프로파일러 측 변경 (`profiler/`를 건드린 경우)

프로파일러 변경은 perf 번들을 재생성할 때까지 시뮬레이터에 나타나지 않습니다. 편집이
파이프라인을 깨뜨리지 않는지 확인하기 위해 작은 프로파일을 실행하세요:

```bash
# vLLM 컨테이너 내에서
MODEL=meta-llama/Llama-3.1-8B HARDWARE=RTXPRO6000 \
    ./profiler/profile.sh
```

그런 다음 단계 1의 smoke 실행으로 시뮬레이터가 여전히 그것을 깔끔하게 로드하는지
확인하세요.

alpha 피팅(`fit_alpha.py`)만 변경했으면, `SKIP_DENSE=1 SKIP_PER_SEQUENCE=1
SKIP_ATTENTION=1 SKIP_MOE=1 ONLY_SKEW=1 ./profiler/profile.sh`를 사용하여 나머지를
재실행하지 않고 `skew_fit.csv`만 갱신할 수 있습니다.

## PR에서 "이것이 재현되어야 함"이 어떻게 보이나

PR 설명에, 실행한 정확한 명령과 출력의 핵심 수치를 포함하세요. 예:

> Validation: `./bench/examples/validate.sh Llama-3.1-8B` → TTFT MAPE 2.1%(2.3%였음),
> TPOT MAPE 1.7%(변화 없음), throughput 1.2%(1.4%였음).

> Smoke: `python -m serving --cluster-config single_node_single_instance.json --dataset
> example_trace.jsonl --num-reqs 10`이 깔끔하게 실행, 출력 CSV에 예상된 10행.

이는 리뷰어에게 재실행할 무언가를 주고, 당신(과 git 로그의 미래 독자)에게 무엇이
확인되었는지의 기록을 줍니다.

## 기존 시나리오가 변경한 것을 커버하지 않을 때

기여가 어떤 번들 시나리오도 사용하지 않는 기능을 추가하면, **PR의 일부로 새 번들
시나리오를 추가하세요.** `configs/cluster/<your_scenario>.json`을 넣고 일치하는 라인을
`serving/run.sh`에 추가하세요. 이는 다음 기여자를 위해 기능을 재현 가능하게 하고 리뷰어에게
사용할 구체적인 것을 줍니다.

커스텀 워크로드가 필요한 기능(새 agentic 데이터셋, 특정 프롬프트 분포)의 경우, `workloads/`
아래에 작은 JSONL을 커밋하고 클러스터 설정 예제에서 참조하세요. 몇 MB를 넘는 것은 아무것도
커밋하지 마세요.

## 다음 단계

- **[PR 워크플로우](./pr-workflow)**: 변경을 패키징하는 방법.
- **[출력 읽기](/docs/simulator/reading-output)**: 요청별 CSV 열이 무엇을 의미하는지(검증 시
  유용).
