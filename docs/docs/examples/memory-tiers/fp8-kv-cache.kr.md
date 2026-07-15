---
title: FP8 KV cache
sidebar_position: 3
---

# FP8 KV cache

> **이것이 보여주는 것:** key와 value를 bf16/fp16(2바이트) 대신 8비트 float(요소당
> 1바이트)로 저장하여 KV cache 메모리 소비를 절반으로 줄임. 더 큰 배치나 더 긴
> 컨텍스트를 위해 NPU 메모리를 확보.

`--kv-cache-dtype fp8`이 그 플래그입니다. 두 가지를 합니다:

1. **트레이스 생성기**가 variant 폴더 조회를 `<dtype>`(예: `bf16`)에서
   `<dtype>-kvfp8`(예: `bf16-kvfp8`)로 교체하여, 어텐션 지연이 FP8-KV 프로파일
   번들에서 오도록 함.
2. **메모리 모델**이 블록별 KV cache 바이트 수를 절반으로 함(`bytes_per_block`이
   `2` 대신 `kv_fp_size = 1`을 사용)으로써, 스케줄러가 같은 `npu_mem`에서 대략 2배의
   활성 토큰을 수용할 수 있게 함.

## 사전 요구 사항

- 시뮬레이터 컨테이너 설정 완료
- `(hardware, model)` 조합에 대한 **`-kvfp8` variant**를 가진 프로파일 번들. 번들된
  RTXPRO6000 perf 데이터는 `bf16` variant만 제공 — 아래 박스 참고.

> ⚠️ **FP8-KV 프로파일 번들이 필요합니다.**
> `profiler/perf/<hardware>/<model>/<variant>-kvfp8/`가 존재하지 않으면, 시뮬레이터가
> 누락된 폴더를 가리키는 명확한 `FileNotFoundError`로 시작 시 종료합니다. 오늘 번들:
>
> | 하드웨어 | 모델 | 제공된 variant |
> | --- | --- | --- |
> | `RTXPRO6000` | `meta-llama/Llama-3.1-8B` | `bf16` |
> | `RTXPRO6000` | `Qwen/Qwen3-32B` | `bf16` |
> | `RTXPRO6000` | `Qwen/Qwen3-30B-A3B-Instruct-2507` | `bf16` |
>
> 오늘 이 예제를 사용하려면, 먼저 `KV_CACHE_DTYPE=fp8 ./profiler/profile.sh`로
> `-kvfp8` variant를 프로파일하고(**[프로파일러 → 하드웨어
> 추가](/docs/profiler/adding-hardware)** 참고) 다시 실행하세요.

## 클러스터 설정

어떤 단일 인스턴스 클러스터 설정이든 동작합니다; FP8 KV는 설정 필드가 아니라 런타임
CLI 플래그입니다. 번들된 간단한 설정을 사용한 예제:

```json title="configs/cluster/single_node_single_instance.json"
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
          "num_npus": 1,
          "tp_size": 1,
          "pd_type": null
        }
      ]
    }
  ]
}
```

## 실행

```bash
python -m serving \
  --cluster-config 'configs/cluster/single_node_single_instance.json' \
  --dtype bfloat16 --kv-cache-dtype fp8 --block-size 16 \
  --dataset 'workloads/example_trace.jsonl' \
  --output 'outputs/fp8_kv_run.csv' \
  --log-interval 1.0
```

두 dtype 플래그가 조합됩니다:

- `--dtype bfloat16`: 가중치는 여전히 bf16(가중치 측 프로파일 variant로 선택됨).
- `--kv-cache-dtype fp8`: KV cache는 fp8. variant 리졸버가 가중치 variant에
  `-kvfp8`을 붙이므로, 이 실행은
  `profiler/perf/RTXPRO6000/meta-llama/Llama-3.1-8B/bf16-kvfp8/`에서 어텐션 지연을
  읽습니다.

## 예상 출력

throughput 로그는 형태가 변하지 않아 보이지만, 같은 배치 크기에서 메모리 풋프린트가
훨씬 작습니다:

```text
[INFO] step=42 batch=16 prompt_t=2.4k tok/s decode_t=860 tok/s
       npu_mem=68.2 GB
```

비교를 위해, 같은 머신에서 같은 워크로드를 `--kv-cache-dtype auto`(= bf16)로
`batch=16`에서 실행하면 OOM이 나거나 메모리 압박 하에 훨씬 작은 배치를
생성했을 것입니다. 토큰당 메모리 비용의 KV-cache 절반이 사라졌습니다.

## 무엇이 흥미로운가

- **KV 바운드 워크로드에서 throughput이 상승합니다.** 긴 컨텍스트 디코드는 KV cache
  메모리가 지배합니다; 이를 절반으로 하면 같은 `npu_mem`에서 유효 배치 크기가 두
  배가 됩니다. 디코드 throughput이 따라옵니다.
- **TTFT가 약간 변합니다.** 프리필 어텐션이 FP8 KV 프로파일을 읽으며, 이는 약간 다른
  토큰당 비용을 가집니다(어텐션 커널이 즉석에서 dtype 변환을 함). 보통 긴 프리필에서
  작은 이득, 짧은 것에서 중립.
- **시뮬레이터로부터의 정확도 주장 없음.** 다른 모든 노브처럼 `--kv-cache-dtype
  fp8`은 *지연 / 메모리* 노브이지 수치 정확도 노브가 아닙니다. 시뮬레이터는 FP8 KV가
  올바른 출력을 생성하는지 실제 vLLM에 대해 검증하지 않습니다; 그것은 vLLM의
  문제입니다. 시뮬레이터는 단지 올바른 바이트와 지연을 부과합니다.

## 관련 예제

- **[Prefix caching](./prefix-caching)**: 직교적이며 종종 결합됨. 토큰당 KV를 절반으로
  하는 것에 더해 prefix 블록 재사용이 메모리 절약을 복합시킴.
- **[CXL 메모리](./cxl-memory)**: 제자리에서 압축하는 대신 2차 계층으로 spill하여
  메모리 압박을 공략하는 또 다른 방법.

## 더 알아보기

- **[시뮬레이터 → KV cache & 메모리](/docs/simulator/scheduling/kv-cache-and-memory)**:
  `bytes_per_block` 공식과 `kv_fp_size`가 스케줄러의 메모리 확인으로 흐르는 방법.
- **[프로파일러 → 출력 번들](/docs/profiler/output-bundle)**: variant 명명(`bf16` vs
  `bf16-kvfp8` vs `fp8` vs `fp8-kvfp8`)과 프로파일러가 각각을 생성하는 방법.
