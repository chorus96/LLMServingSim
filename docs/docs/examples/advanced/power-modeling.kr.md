---
title: 전력 모델링
sidebar_position: 1
---

# 전력 모델링

> **이것이 보여주는 것:** 노드별 전력 모델을 켜서 시뮬레이터가 throughput 로그에
> 실시간 와트를, 실행 끝에 구성 요소별 에너지 분석을 내도록 함.

전력 모델은 opt-in입니다: 노드는 설정에 `power:` 블록이 포함될 때만 전력을
추적합니다. 번들된 `single_node_power_instance.json`이 바로 실행 가능한 예제입니다.

## 사전 요구 사항

- 시뮬레이터 컨테이너 설정 완료
- `meta-llama/Llama-3.1-8B`용 번들 RTXPRO6000 프로파일(추가 프로파일링 불필요)

## 클러스터 설정

`configs/cluster/single_node_power_instance.json`은 일반적인 `instances`와 함께
노드에 `power:` 블록을 추가합니다:

```json title="configs/cluster/single_node_power_instance.json (발췌)"
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
          "pd_type": null,
          "tp_size": 1
        }
      ],
      "power": {
        "base_node_power": 60,
        "npu": {
          "RTXPRO6000": {
            "idle_power": 35,
            "standby_power": 300,
            "active_power": 600,
            "standby_duration": 18
          }
        },
        "cpu":     {"idle_power": 10, "active_power": 200, "util": 0.15},
        "dram":    {"dimm_size": 32,  "idle_power": 2.0,   "energy_per_bit": 6.0},
        "link":    {"num_links": 1,   "idle_power": 5,     "energy_per_bit": 4.0},
        "nic":     {"num_nics": 1,    "idle_power": 20},
        "storage": {"num_devices": 2, "idle_power": 5}
      }
    }
  ]
}
```

`npu.<hardware>` 키는 인스턴스의 `hardware` 필드로 전력 계수를 조회하므로, 다중
하드웨어 클러스터는 하드웨어 유형당 하나의 항목을 나열합니다.

필드별 스키마(`base_node_power`, `idle_power`, `standby_duration`, `energy_per_bit`
...)는 [클러스터 설정 → power](/docs/reference/cluster-config)를 참고하세요.

## 실행

```bash
python -m serving \
  --cluster-config 'configs/cluster/single_node_power_instance.json' \
  --dtype float16 --block-size 16 \
  --dataset 'workloads/example_trace.jsonl' \
  --output 'outputs/power_run.csv' \
  --log-interval 1.0
```

새 CLI 플래그는 필요 없습니다. 클러스터 설정의 `power:` 블록 존재가 트리거입니다;
전력을 추적하지 않는 베이스라인 실행을 위해서는 블록을 제거하세요.

## 예상 출력

throughput 로그에 `power=` 필드(와트 단위)가 추가됩니다:

```text
[INFO] step=42 batch=8 prompt_t=1.2k tok/s decode_t=420 tok/s
       npu_mem=88.4 GB power=712 W
[INFO] step=43 batch=8 prompt_t=1.1k tok/s decode_t=440 tok/s
       npu_mem=88.4 GB power=698 W
```

`power`는 NPU / CPU / DRAM / link / NIC / storage / base에 걸쳐 합산된 **순간** 총
노드 전력입니다.

실행이 끝나면 시뮬레이터가 구성 요소별 에너지 분석을 출력합니다:

```text
─────── Power summary (node 0) ───────
   NPU active     :   12,453 J  (78%)
   NPU standby    :    1,012 J   (6%)
   NPU idle       :       89 J   (1%)
   CPU            :    1,233 J   (8%)
   DRAM           :      442 J   (3%)
   Link           :      388 J   (2%)
   Base + NIC + storage : 332 J  (2%)
   ─────────────────────────────────
   Total energy   :   15,949 J
```

이 분석이 실행 가능한 출력입니다. `NPU active`가 지배하는 실행은 compute-bound;
`NPU idle`이 상당한 실행은 저활용; `Link` 에너지가 불균형적으로 큰 실행은
ALLREDUCE-bound(`tp_size > 1`일 때 확인할 가치가 있음)입니다.

## 무엇이 흥미로운가

- **Throughput vs 와트 트레이드오프.** `--max-num-seqs`를 올리면 throughput과 `NPU
  active` / `standby` 시간이 함께 상승하지만, 기울기는 워크로드마다 다릅니다 —
  토큰당 에너지가 디코드 위주 부하에서는 개선되고 프리필 위주에서는 나빠집니다.
- **Standby vs idle 간극.** `standby_duration`(커널 종료 후 ns)은 NPU가 얼마나 자주
  `idle_power`로 돌아가는지 결정합니다. 버스트 워크로드는 `idle`에 더 많은 시간을
  씀; 정상 상태 워크로드는 `standby` / `active`에 머무릅니다. `NPU idle > NPU
  standby`는 보통 워크로드가 GPU를 포화시키지 않음을 의미합니다.
- **Base-node 전력은 상수입니다.** 호스트 측 소비(`base_node_power`)는 시뮬레이터가
  무엇을 하든 의존하지 않습니다; 에너지 효율성 비교가 고려해야 할 상시 켜진
  오버헤드입니다.

## 관련 예제

- **[서브 배치 인터리빙](./sub-batch-interleaving)** — 전력 모델과 깔끔하게 짝지어짐.
  PIM 어텐션을 GPU 계산과 오버랩하면 throughput과 에너지 분석이 모두 변합니다.
- **[CXL 메모리](../memory-tiers/cxl-memory)** — `cxl_mem` 장치와 장치별 배치 규칙을
  추가하면 throughput 로그에 `cxl_mem=...` 필드가 추가됨; 에너지 요약에 CXL 전송
  에너지가 포함됨.

## 더 알아보기

- **[시뮬레이터 → 전력 모델](/docs/simulator/specialized/power-model)**: 구성
  요소별 수식, NPU 상태 기계, `standby_duration`이 고려되는 방법.
- 구현은 `serving/core/power_model.py`에 있습니다.
