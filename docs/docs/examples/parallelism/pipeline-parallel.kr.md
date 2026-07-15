---
title: 파이프라인 병렬 (PP)
sidebar_position: 2
---

# 파이프라인 병렬 (PP)

> **이것이 보여주는 것:** 모델의 디코더 레이어를 GPU에 걸쳐 분할하여(GPU당 하나의
> 스테이지) 각 반복이 마이크로 배치로 파이프라인을 통과하게 함.

PP는 TP와 직교하는 축입니다: TP는 레이어 *내부에서* 가중치를 샤딩하고, PP는 장치
*간에* 레이어를 샤딩합니다. 각 GPU는 디코더 블록 스택의 연속된 구간을 실행하고 중간
activation을 다음 스테이지에 넘깁니다. 스케줄러는 in-flight 배치를 `pp_size`로
상한하고, Chakra는 각 반복의 레이어 리스트를 경계에서의 send/recv와 함께 스테이지
NPU에 걸쳐 분할합니다.

## 사전 요구 사항

- 시뮬레이터 컨테이너 설정 완료
- `meta-llama/Llama-3.1-8B`용 번들 RTXPRO6000 프로파일

## 클러스터 설정

PP 전용 번들 설정은 없습니다; 파이프라인 병렬은 다중 GPU 인스턴스에서 `pp_size`를
바꿔 실행합니다. 다른 설정 옆에 `single_node_pp_instance.json`을 넣으세요:

```json title="configs/cluster/single_node_pp_instance.json"
{
  "num_nodes": 1,
  "link_bw": 16,
  "link_latency": 20000,
  "nodes": [
    {
      "num_instances": 1,
      "cpu_mem": {"mem_size": 512, "mem_bw": 256, "mem_latency": 0},
      "instances": [
        {
          "model_name": "meta-llama/Llama-3.1-8B",
          "hardware": "RTXPRO6000",
          "npu_mem": {"mem_size": 96, "mem_bw": 1597, "mem_latency": 0},
          "num_npus": 2,
          "tp_size": 1,
          "pp_size": 2,
          "pd_type": null
        }
      ]
    }
  ]
}
```

중요한 두 필드:

- `num_npus: 2`, `tp_size: 1`, `pp_size: 2`: 불변식은 `num_npus = tp_size *
  pp_size`이므로, 시뮬레이터가 모델을 두 파이프라인 스테이지(각각 자체 GPU에)로
  분할하며 스테이지 내 TP는 없음.
- 결합된 TP × PP(예: 4 GPU를 `tp=2, pp=2`로)의 경우, `num_npus: 4, tp_size: 2,
  pp_size: 2` 설정.

## 실행

```bash
python -m serving \
  --cluster-config 'configs/cluster/single_node_pp_instance.json' \
  --dtype float16 --block-size 16 \
  --dataset 'workloads/example_trace.jsonl' \
  --output 'outputs/pp2_run.csv' \
  --log-interval 1.0
```

새 CLI 플래그 없음 — 병렬화 차수는 전적으로 클러스터 설정으로 구동됩니다.

## 예상 출력

throughput 로그는 표준 단일 인스턴스 실행처럼 보입니다:

```text
[INFO] step=20 batch=8 prompt_t=1.4k tok/s decode_t=540 tok/s npu_mem=44.0 GB
[INFO] step=21 batch=8 prompt_t=1.5k tok/s decode_t=560 tok/s npu_mem=44.1 GB
```

TP=1 베이스라인 대비 주목할 두 가지:

- **`npu_mem`이 대략 절반**(각 GPU가 디코더 레이어의 절반을 보유하므로, 장치당
  가중치 + KV cache가 줄어듦).
- 짧은 버스트 동안 **`batch`가 더 낮은 값에서 포화**할 수 있음 — 스케줄러가
  `inflight == pp_size`가 되면 발행을 멈추기 때문. 이는 파이프라인에 작업을 과잉
  주입하는 것을 막는 back-pressure입니다.

## 무엇이 흥미로운가

- **메모리 분할은 실제입니다.** 각 스테이지는 디코더 레이어의 자기 조각만 보유하므로,
  GPU당 가중치 + KV-cache 풋프린트가 대략 1/`pp_size`로 줄어듭니다. PP=2는 TP=1에
  맞지 않는 모델을 수용하게 해줍니다.
- **스테이지 간 activation 전송은 실제입니다.** 클러스터 설정의 `link_bw` /
  `link_latency`를 올리면 반복 시간이 눈에 띄게 움직입니다 — Chakra가 스테이지 사이에
  삽입하는 send/recv 노드가 다른 collective처럼 시뮬레이션된 네트워크를 통과하기
  때문. 이를 사용해 인터커넥트 선택이 PP 스케일링에 어떻게 영향을 주는지 연구하세요.
- **파이프라인 깊이가 in-flight 배치를 상한합니다.** `inflight ≤ pp_size`가 PP 구동
  스케줄링 제약입니다. `pp_size=2`와 6개 배치를 허용하는 토큰 예산으로, 스케줄러가
  파이프라인에 한 번에 최대 2개 배치를 큐잉하는 것을 보게 됩니다. 정상 상태 파이프라인
  오버랩(스테이지 0의 배치 *k+1*이 배치 *k*가 스테이지 1에 있는 동안)은 ASTRA-Sim이
  각 스테이지의 `.et` 파일을 독립적으로 실행함으로써 자연스럽게 나타납니다.
- **모델링되지 않는 것.** 단일 반복 내에서 배치는 스테이지를 순서대로 통과하는 단일
  단위입니다 — 하나의 반복 *내부에* 마이크로 배치 분할이 없고, 파이프라인
  스케줄(1F1B, interleaved 등)의 선택도 없습니다. 따라서 그런 스케줄에서 볼 수 있는
  fill/drain 버블은 나타나지 않습니다; 파이프라이닝 이점은 전적으로 연속된 반복을
  `pp_size`까지 오버랩하는 데서 옵니다.

## 관련 예제

- **[텐서 병렬](./tensor-parallel)**: 레이어 내 상대. TP × PP 조합은 유효하며 대규모에서
  흔합니다.
- **[다중 인스턴스 LOAD 라우팅](../disaggregated/multi-instance)**: 다음 단계 스케일링
  — 전체 TP × PP 그룹을 인스턴스에 걸쳐 복제.

## 더 알아보기

- **[시뮬레이터 → 병렬화 메커니즘](/docs/simulator/parallelism-mechanics)**:
  `num_npus`, `tp_size`, `pp_size`가 검증되고 스케줄러 / 트레이스 생성기를 통해
  전달되는 방법.
- PP `inflight` 리스트는 `serving/core/scheduler.py`에 있습니다; 스테이지별 레이어
  분할과 send/recv 삽입은
  `astra-sim/extern/graph_frontend/chakra/src/converter/llm_converter.py`
  (`convert_common` / `convert_prefill`)에 있습니다.
