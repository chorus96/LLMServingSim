---
title: 검증
sidebar_position: 3
description: LLMServingSim의 출력이 실제 vLLM과 어떻게 비교되는가
---

# 검증

LLMServingSim은 **번들된 `(hardware, model)` 조합**에 대해 실제 vLLM과 end-to-end로
검증됩니다. 아래 수치는 300개 요청 ShareGPT 재실행을 RTXPRO6000에서 vLLM v0.19.0과
시뮬레이터 양쪽으로 실행한 후, `python -m bench validate`로 요청별 및 틱별 지표를
비교한 것입니다.

> **자신의 변경을 검증하고 싶으신가요?** 회귀 워크플로우는
> **[기여자용 → 변경 사항 검증](/docs/contributor/validating-changes)**을 참고하세요.

## 설정

| 노브 | 값 |
| --- | --- |
| **워크로드** | 300개 ShareGPT 파생 요청, ~10 sps 푸아송 도착 |
| **하드웨어** | RTXPRO6000 (단일 노드, `profiler/perf/RTXPRO6000/`의 프로파일 번들) |
| **vLLM 버전** | `v0.19.0` (bench 컨테이너가 사용하는 pin) |
| **블록 크기** | 16 |
| **엔진 플래그** | 클러스터 설정이 달리 지시하는 경우를 제외한 기본값 |
| **클러스터 설정** | `bench/examples/configs/<model>.json` |

입력과 출력(vLLM 토큰 ID, 샘플링 파라미터, 요청별 타이밍)은 `bench`의 엄격한
재실행 경로를 통해 고정되어, 두 실행이 정확히 같은 프롬프트를 같은 순서로
처리합니다.

## 핵심 수치

현재 번들된 세 설정에서 지표별 실제 vLLM 대비 평균 오차:

| 모델 | 병렬화 | TTFT 평균 | TPOT 평균 | Latency 평균 |
| --- | --- | --- | --- | --- |
| Llama-3.1-8B                | TP=1 dense       | -0.3% | +0.7% | +0.4% |
| Qwen3-32B                   | TP=2 dense       | +2.4% | +1.7% | +2.0% |
| Qwen3-30B-A3B-Instruct-2507 | DP=2 × EP=2 MoE  | -1.5% | +1.1% | +0.9% |

세 경우 모두 **TTFT / TPOT / latency 평균이 vLLM의 ~2.5% 이내에 머무르며**, DP+EP
MoE 경로는 dense TP 경로만큼 촘촘하게 vLLM을 추적합니다. 백분위별 수치(P50 / P90 /
P95 / P99)는
[`bench/examples/`](https://github.com/casys-kaist/LLMServingSim/tree/main/bench/examples)
아래의 모델별 `summary.txt` 파일에 있습니다.

## 모델별 결과

### Llama-3.1-8B (TP=1 dense)

Throughput 타임라인, vLLM(주황) vs 시뮬레이터(파랑):

![Llama-3.1-8B throughput](/img/validation/llama-3.1-8b-throughput.png)

vLLM 대비 핵심 오차:

| 지표 | vLLM | Sim | 차이 |
| --- | --- | --- | --- |
| TTFT mean    |  7.10 s   |  7.07 s   | **-0.3%** |
| TTFT P99     | 19.76 s   | 19.96 s   | +1.0% |
| TPOT mean    | 32.5 ms   | 32.7 ms   | **+0.7%** |
| TPOT P99     | 37.3 ms   | 38.1 ms   | +2.1% |
| Latency mean | 28.20 s   | 28.31 s   | **+0.4%** |
| Latency P99  | 37.64 s   | 37.96 s   | +0.8% |

단일 인스턴스 dense Llama가 가장 단순한 설정입니다. 시뮬레이터는 TTFT 평균을 0.3%
이내로 맞추고 TPOT과 end-to-end latency를 ~1% 이내로 추적합니다.

### Qwen3-32B (TP=2 dense)

Throughput 타임라인:

![Qwen3-32B throughput](/img/validation/qwen3-32b-throughput.png)

vLLM 대비 핵심 오차:

| 지표 | vLLM | Sim | 차이 |
| --- | --- | --- | --- |
| TTFT mean    | 36.91 s    | 37.81 s    | **+2.4%** |
| TTFT P99     | 93.35 s    | 95.25 s    | +2.0% |
| TPOT mean    |  80.3 ms   |  81.7 ms   | **+1.7%** |
| TPOT P99     |  97.1 ms   |  99.2 ms   | +2.2% |
| Latency mean | 90.41 s    | 92.23 s    | **+2.0%** |
| Latency P99  | 126.34 s   | 129.30 s   | +2.3% |

TP=2는 `o_proj` / `down_proj`의 dense ALLREDUCE collective를 사용합니다. 평균과
P99가 ~2.5% 이내에 들어옵니다; 시뮬레이터는 반복별 dense 계산이 이제 청크 프리필
토큰 수를 더 적극적으로 회계 처리하기 때문에 약간 과대 예측합니다.

### Qwen3-30B-A3B-Instruct-2507 (DP=2 × EP=2 MoE)

Throughput 타임라인:

![Qwen3-30B-A3B-Instruct-2507 throughput](/img/validation/qwen3-30b-a3b-throughput.png)

vLLM 대비 핵심 오차:

| 지표 | vLLM | Sim | 차이 |
| --- | --- | --- | --- |
| TTFT mean    |  1.09 s    |  1.07 s    | **-1.5%** |
| TTFT P99     |  9.59 s    | 10.04 s    | +4.7% |
| TPOT mean    | 47.3 ms    | 47.8 ms    | **+1.1%** |
| TPOT P99     | 53.3 ms    | 54.7 ms    | +2.7% |
| Latency mean | 32.34 s    | 32.64 s    | **+0.9%** |
| Latency P99  | 43.90 s    | 44.26 s    | +0.8% |

이것은 분리(disaggregated) 경로입니다: 두 인스턴스에 걸친 data-parallel, 각 인스턴스
내의 expert-parallel, 그리고 2D ASTRA-Sim 토폴로지에서의 wave-synchronized
ALLTOALL. TTFT P50은 더 시끄럽지만(시뮬레이터가 매우 짧은 프리필을 약간 더 빨리
끝냄), 평균과 tail latency는 vLLM과 ~3% 이내로 정렬됩니다.

## 로컬에서 재현

bench 모듈에는 시뮬레이터 측을 재실행하고 커밋된 vLLM 산출물에 대해 비교를
재실행하는 재현 스크립트가 포함되어 있습니다:

```bash
# Sim 측: bench/examples/<model>/outputs/sim.csv 기록
./bench/examples/run.sh Llama-3.1-8B
./bench/examples/run.sh Qwen3-32B
./bench/examples/run.sh Qwen3-30B-A3B-Instruct-2507

# 비교: bench/examples/<model>/validation/{summary.txt, *.png} 기록
./bench/examples/validate.sh Llama-3.1-8B
./bench/examples/validate.sh Qwen3-32B
./bench/examples/validate.sh Qwen3-30B-A3B-Instruct-2507
```

검증 단계는 throughput / latency / requests 플롯과 핵심 요약을 재생성합니다.
(`bench/examples/<model>/vllm/` 아래 커밋된 산출물을 재사용하는 대신) vLLM 자체를
재실행하려면 vLLM 컨테이너 내부에서 `python -m bench run`을 사용하세요; 전체
레이아웃은
[`bench/README.md`](https://github.com/casys-kaist/LLMServingSim/blob/main/bench/README.md)를
참고하세요.

## 다음 단계

- **[기여자용 → 변경 사항 검증](/docs/contributor/validating-changes)**: PR을 열기
  전에 실행하는 3계층 확인(smoke → scenario → bench validate)과 어떤 회귀를
  플래그할지.
- **[시뮬레이터 → 출력 읽기](/docs/simulator/reading-output)**: 요청별 CSV의 모든
  열이 무엇을 의미하며 그로부터 자신의 지표를 유도하는 방법.
