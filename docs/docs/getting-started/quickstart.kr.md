---
sidebar_position: 3
title: 빠른 시작
---

# 빠른 시작

1분 안에 첫 end-to-end 시뮬레이션을 실행하세요.

이 설명은 [설치 → 시뮬레이터 설정](./installation/simulator)을 마쳤고
`/app/LLMServingSim`의 시뮬레이터 컨테이너 안에 있다고 가정합니다.

## 예제 실행

```bash
python -m serving \
  --cluster-config 'configs/cluster/single_node_single_instance.json' \
  --dtype float16 --block-size 16 \
  --dataset 'workloads/example_trace.jsonl' \
  --output 'outputs/example_single_run.csv' \
  --log-interval 1.0
```

이게 전부입니다. 시뮬레이터는:

1. `configs/cluster/single_node_single_instance.json`에서 클러스터 토폴로지를
   로드(TP=1로 Llama-3.1-8B를 실행하는 단일 RTXPRO6000 GPU).
2. `workloads/example_trace.jsonl`에서 도착 시각에 따라 요청을 스트리밍.
3. 각 스케줄링 반복마다 ASTRA-Sim을 스텝하여 사이클 수를 얻음.
4. 요청별 지연 지표를 `outputs/example_single_run.csv`에 기록.

throughput, 메모리, 전력 라인이 대략 초당 한 번 출력됩니다. 실행이 끝난 후:

```bash
head outputs/example_single_run.csv
```

는 요청별 출력(request id, prompt 및 decode 토큰, TTFT, TPOT, end-to-end 지연 등)을
보여줍니다.

## 플래그의 의미

| 플래그 | 하는 일 |
| --- | --- |
| `--cluster-config` | 클러스터 토폴로지 + 하드웨어. ASTRA-Sim 입력 파일을 자동 생성. |
| `--dtype` | 모델 가중치 정밀도(`float16`, `bfloat16`, `float32`, `int8`). 일치하는 프로파일 번들을 선택. |
| `--block-size` | KV-cache 블록 크기(토큰). 기본 `16`. |
| `--dataset` | 요청(또는 agentic 세션)의 JSONL 파일. |
| `--output` | 요청별 지표를 기록할 위치. |
| `--log-interval` | throughput / 메모리 / 전력 요약 라인을 출력하는 주기(초). |

전체 플래그 목록은 [레퍼런스 → CLI 플래그](/docs/reference/cli-flags)에 있습니다.

## 다른 시나리오 시도

`serving/run.sh`는 다중 인스턴스, 프리필/디코드 분리, EP를 갖춘 MoE, prefix
caching, CXL 메모리, PIM offload, 서브 배치 인터리빙 등 몇 가지 작동 예제를
제공합니다:

```bash
./serving/run.sh
```

그 스크립트의 각 블록은 독립적이며 자신의 스크립트로 복사할 준비가 되어 있습니다.
이를 구동하는 클러스터 설정을 둘러보세요:

```bash
ls configs/cluster/
```

## 다음 단계

- 시뮬레이터가 내부적으로 어떻게 실행되는지 이해하려면
  **[시뮬레이터 → 아키텍처 개요](/docs/simulator/architecture)**.
- `*.csv`의 지표를 이해하려면
  **[시뮬레이터 → 출력 읽기](/docs/simulator/reading-output)**.
- 자신의 트레이스로 시뮬레이터를 구동하려면
  **[워크로드 → JSONL 형식](/docs/workloads/jsonl-format)**.
- 새 하드웨어나 모델을 추가하려면 **[프로파일러 개요](/docs/profiler/overview)**.
