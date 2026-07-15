---
title: 서브 배치 인터리빙
sidebar_position: 2
---

# 서브 배치 인터리빙

> **이것이 보여주는 것:** 각 배치를 절반으로 나누어 한 절반에서 GPU dense 레이어를,
> 다른 절반에서 PIM 어텐션을 실행하여 어느 장치도 유휴 상태로 있지 않게 함.

[PIM 어텐션 offload](../disaggregated/pim-attention-offload) 자체는 종종 프리필
TTFT를 악화시킵니다: GPU가 dense 레이어를 끝내고 PIM이 어텐션을 따라잡기를
기다립니다. 서브 배치 인터리빙이 이를 해결합니다. 스케줄러가 배치를 두
절반(`BATCH_1`과 `BATCH_2`)으로 자르고, 트레이스 생성기가 한 절반의 GPU 작업을 다른
절반의 PIM 작업과 번갈아 합니다. 두 장치가 바쁘게 유지되고; 총 반복 시간이 대략 둘
중 느린 쪽으로 떨어집니다.

이것은 PIM offload의 자연스러운 후속입니다. **`--enable-attn-offloading` 없이
활성화하지 마세요.**

## 사전 요구 사항

- 시뮬레이터 컨테이너 설정 완료
- `meta-llama/Llama-3.1-8B`용 번들 RTXPRO6000 프로파일
- PIM 장치 설정(`configs/pim/DDR4_8GB_3200_pim/`); 번들된
  `single_node_pim_instance.json`이 이미 이를 참조

## 클러스터 설정

[PIM 어텐션 offload](../disaggregated/pim-attention-offload)와 동일한 설정 —
`configs/cluster/single_node_pim_instance.json`. 설정 변경이 필요 없습니다; 서브
배치 인터리빙은 런타임 CLI 플래그입니다.

## 실행

```bash
python -m serving \
  --cluster-config 'configs/cluster/single_node_pim_instance.json' \
  --dtype float16 --block-size 16 \
  --enable-attn-offloading \
  --enable-sub-batch-interleaving \
  --dataset 'workloads/example_trace.jsonl' \
  --output 'outputs/pim_sub_batch_run.csv' \
  --log-level WARNING
```

두 플래그가 함께 작동합니다:

- `--enable-attn-offloading`은 트레이스 내에서 GPU 어텐션 커널을 PIM 커널로 교체.
- `--enable-sub-batch-interleaving`은 그다음 각 반복의 배치를 두 절반으로 나누고 한
  절반의 GPU dense 레이어가 다른 절반의 PIM 어텐션과 오버랩되는 인터리빙된 트레이스를
  생성.

## 예상 출력

throughput 로그가 두 장치 모두 로드된 것을 보여줍니다:

```text
[INFO] step=10 batch=8 prompt_t=1.4k tok/s decode_t=620 tok/s
       npu_mem=63.4 GB pim_busy=78% gpu_busy=82%
[INFO] step=11 batch=8 prompt_t=1.4k tok/s decode_t=640 tok/s
       npu_mem=63.4 GB pim_busy=80% gpu_busy=80%
```

순수 PIM 실행(`--enable-sub-batch-interleaving` 없이)과 비교하세요: GPU는 이전에 PIM을
기다리며 긴 유휴 구간이 있었지만; 이제 `pim_busy`와 `gpu_busy` 모두 70대 후반 / 80대에
고르게 유지됩니다.

`outputs/pim_sub_batch_run.csv`는 다른 실행과 같은 요청별 스키마를 가집니다; 변하는
것은 열 집합이 아니라 반복별 지연 시간입니다.

## 무엇이 흥미로운가

- **프리필 TTFT가 회복됩니다.** 순수 PIM offload는 프리필을 악화시킵니다(PIM의
  채널당 계산이 GPU의 병렬 어텐션 유닛보다 좁음). 인터리빙으로 GPU의 dense 작업이
  PIM 프리필 비용의 대부분을 숨깁니다.
- **디코드는 대부분 변하지 않습니다.** 디코드 어텐션은 이미 메모리 바운드이고
  PIM 친화적이므로, 서브 배치 인터리빙은 디코드 위주 워크로드에 별로 추가하지
  않습니다. 이득은 프리필 측에 집중됩니다.
- **절반 배치 단위가 유일한 노브입니다.** 스케줄러는 항상 50/50으로 나눕니다. 배치에
  요청이 하나뿐이면 인터리빙이 조용히 no-op이 됩니다(단일 요청을 요청별 의미론을
  깨지 않고 두 절반으로 나눌 수 없음).
- **트레이스 태그.** 생성된 트레이스 파일(`astra-sim/inputs/runs/<run_id>/trace/...`)을
  읽으면, 각 레이어가 일반적인 `NONE` 대신 `BATCH_1` 또는 `BATCH_2` misc 태그를
  담습니다. 인터리빙이 실제로 생성되었음을 확인합니다.

## 관련 예제

- **[PIM 어텐션 offload](../disaggregated/pim-attention-offload)** — 사전 요구 사항.
  서브 배치 인터리빙은 그 위의 회복 계층입니다.
- **[전력 모델링](./power-modeling)**: 이 예제와 함께 `power:` 블록을 켜면 인터리빙이
  NPU active와 PIM 계산에 걸쳐 에너지를 어떻게 재분배하는지 보여줍니다.

## 더 알아보기

- **[시뮬레이터 → PIM offload](/docs/simulator/specialized/pim-offload)**: PIM 장치
  모델과 트레이스 생성기가 `PIM {channel}` / `PIM END` 마커를 생성하는 방법. 서브
  배치 인터리빙은 이 위에 있습니다.
- **[레퍼런스 → 트레이스 형식](/docs/reference/trace-format)**: `BATCH_1` /
  `BATCH_2` misc 태그 의미론.
