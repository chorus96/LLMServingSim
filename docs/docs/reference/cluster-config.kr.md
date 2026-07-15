---
sidebar_position: 1
title: 클러스터 설정
---

# 클러스터 설정 스키마

`--cluster-config`로 전달되는 JSON 파일의 필드별 정식 스키마입니다. 예제와 함께
안내되는 설명은 **[예제 → 클러스터 설정
설명](/docs/examples/cluster-config-explained)**을 참고하세요. 이 페이지는 **조회
레퍼런스**입니다: 모든 필드, 모든 타입, 모든 기본값.

## 파일 위치

설정은 `configs/cluster/<name>.json`에 있습니다. 시뮬레이터는 시작 시 파일을 한 번
읽고 `serving/core/config_builder.py`가 파생된 ASTRA-Sim 입력 파일(`network.yml`,
`system.json`, `memory_expansion.json`)을 생성합니다.

## 최상위

```json
{
  "num_nodes": 1,
  "link_bw": 16,
  "link_latency": 20000,
  "nodes": [...],
  "cxl_mem": {...}
}
```

| 필드 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `num_nodes` | int | ✓ |  | 클러스터의 물리 노드 수 |
| `link_bw` | float 또는 float[] | ✓ |  | **GB/s** 단위 ASTRA-Sim 토폴로지 링크 대역폭. 스칼라는 모든 토폴로지 차원에 적용; 배열은 최종 `network.yml::npus_count` 랭크와 일치해야 함 |
| `link_latency` | float 또는 float[] | ✓ |  | **ns** 단위 ASTRA-Sim 토폴로지 링크 지연 시간. 스칼라는 모든 토폴로지 차원에 적용; 배열은 최종 `network.yml::npus_count` 랭크와 일치해야 함 |
| `nodes` | array | ✓ |  | 길이가 `num_nodes`와 같아야 함 |
| `cxl_mem` | object | 선택 | 없음 | CXL 메모리 확장(아래 참고) |

예: `network.yml`이 결국 `npus_count: [4, 2]`가 되면, `link_bw: [900, 100]`과
`link_latency: [0, 20000]`을 설정하여 토폴로지 차원별로 다른 대역폭/지연 시간을
할당할 수 있습니다.

## `cxl_mem` (최상위, 선택)

```json
"cxl_mem": {
  "mem_size": 1024,
  "mem_bw": 60,
  "mem_latency": 250,
  "num_devices": 4
}
```

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `mem_size` | float | ✓ | 장치당 **GB** 단위 용량 |
| `mem_bw` | float | ✓ | 장치당 **GB/s** 단위 대역폭 |
| `mem_latency` | float | ✓ | **ns** 단위 접근 지연 시간 |
| `num_devices` | int | ✓ | CXL 장치 수(`cxl:0`부터 `cxl:N-1`까지) |

존재할 때, 인스턴스는 `placement` 필드에서 `cxl:N`을 참조할 수 있습니다.

## 노드별 (`nodes[i]`)

```json
{
  "num_instances": 2,
  "cpu_mem": {"mem_size": 512, "mem_bw": 256, "mem_latency": 0},
  "instances": [...],
  "power": {...},
  "cpu_mem.pim_config": "DDR4_8GB_3200_pim"
}
```

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `num_instances` | int | ✓ | 이 노드의 서빙 인스턴스 수 |
| `cpu_mem` | object | ✓ | 호스트 CPU 메모리 설정(아래 참고) |
| `instances` | array | ✓ | 길이가 `num_instances`와 같아야 함 |
| `power` | object | 선택 | 전력 모델 설정(아래 참고) |

### `cpu_mem`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `mem_size` | float | ✓ | **GB** 단위 호스트 CPU 메모리 용량 |
| `mem_bw` | float | ✓ | **GB/s** 단위 CPU 메모리 대역폭 |
| `mem_latency` | float | ✓ | **ns** 단위 CPU 메모리 지연 시간 |
| `pim_config` | string | 선택 | `configs/pim/`의 PIM 장치 설정 이름. **[PIM 설정](./pim-config)** 참고 |

### `power` (선택)

이 노드에서 전력 모델을 활성화합니다. 전체 스키마는 **[예제 → 전력
모델링](/docs/examples/advanced/power-modeling)**을 참고하세요. 최상위 구조:

```json
"power": {
  "base_node_power": 60,
  "npu": {"<hardware>": {...}},
  "cpu": {...},
  "dram": {...},
  "link": {...},
  "nic": {...},
  "storage": {...}
}
```

| 하위 필드 | 필수 | 설명 |
| --- | --- | --- |
| `base_node_power` | ✓ | **W** 단위 상시 켜진 호스트 플랫폼 전력 |
| `npu.<hardware>.idle_power` | ✓ | NPU idle 와트 |
| `npu.<hardware>.standby_power` | ✓ | NPU 계산 후 standby 와트 |
| `npu.<hardware>.active_power` | ✓ | NPU 활성 계산 와트 |
| `npu.<hardware>.standby_duration` | ✓ | 계산 후 standby에 머무는 시간, **ns** |
| `cpu.idle_power`, `cpu.active_power`, `cpu.util` | ✓ | CPU 기준선 + 사용률 비율 |
| `dram.dimm_size`, `dram.idle_power`, `dram.energy_per_bit` | ✓ | DIMM 크기, idle 전력, 비트당 에너지 |
| `link.num_links`, `link.idle_power`, `link.energy_per_bit` | ✓ | 네트워크 링크 전력 |
| `nic.num_nics`, `nic.idle_power` | ✓ | NIC 수와 기준선 |
| `storage.num_devices`, `storage.idle_power` | ✓ | 스토리지 장치 |

## 인스턴스별 (`instances[i]`)

```json
{
  "model_name": "Qwen/Qwen3-32B",
  "hardware": "RTXPRO6000",
  "npu_mem": {"mem_size": 96, "mem_bw": 1597, "mem_latency": 0},
  "num_npus": 2,
  "tp_size": 2,
  "pp_size": 1,
  "ep_size": 1,
  "dp_group": null,
  "pd_type": null,
  "max_num_seqs": 128,
  "max_num_batched_tokens": 2048,
  "placement": {...}
}
```

### 필수 필드

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `model_name` | string | HF id. `configs/model/<model_name>.json`의 설정과 일치해야 함(**[모델 설정](./model-config)** 참고) |
| `hardware` | string | 하드웨어 라벨. `profiler/perf/<hardware>/`와 일치해야 함 |
| `npu_mem.mem_size` | float | **GB** 단위 GPU별 NPU 메모리 |
| `npu_mem.mem_bw` | float | **GB/s** 단위 GPU별 NPU 메모리 대역폭 |
| `npu_mem.mem_latency` | float | **ns** 단위 GPU별 NPU 메모리 지연 시간 |
| `pd_type` | string \| null | `"prefill"`, `"decode"`, 또는 `null`(통합) |

### 병렬화 (`num_npus` / `tp_size` 중 최소 하나)

| 필드 | 타입 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `num_npus` | int | `tp_size * pp_size`에서 유추 | 이 인스턴스의 총 GPU 수 |
| `tp_size` | int | `num_npus // pp_size`에서 유추 | 텐서 병렬 차수 |
| `pp_size` | int | `1` | 파이프라인 병렬 차수 |
| `ep_size` | int | `tp_size`(MoE) / `1`(dense) | Expert 병렬 차수 |
| `dp_group` | string \| null | `null` | 그룹 ID. 같은 문자열을 가진 인스턴스는 인스턴스 간 ALLTOALL로 expert를 공유 |

**제약:**

- `num_npus == tp_size * pp_size` (항상)
- `dp_group` 없이: `ep_size <= tp_size`
- MoE의 경우: `ep_size`는 `num_local_experts`를 나누어떨어져야 함

### 런타임 오버라이드 (선택)

이 필드들은 이 인스턴스에 대해서만 일치하는 `python -m serving` CLI 플래그를
오버라이드합니다. 생략된 필드는 CLI 값을 유지합니다; `dtype`의 경우 생략된 CLI
값은 여전히 모델 설정의 `torch_dtype`으로 폴백합니다.

| 필드 | 타입 | CLI 폴백 | 설명 |
| --- | --- | --- | --- |
| `max_num_seqs` | int | `--max-num-seqs` | 이 인스턴스의 최대 활성 시퀀스. `0`은 무제한 |
| `max_num_batched_tokens` | int | `--max-num-batched-tokens` | 이 인스턴스의 반복당 토큰 예산. `0`은 무제한 |
| `long_prefill_token_threshold` | int | `--long-prefill-token-threshold` | 청크 프리필의 요청별 청크 상한 |
| `block_size` | int | `--block-size` | KV-cache 블록 크기(토큰) |
| `dtype` | string | `--dtype` | 이 인스턴스의 가중치/프로파일 dtype |
| `kv_cache_dtype` | string | `--kv-cache-dtype` | 메모리 회계 및 프로파일 variant 선택을 위한 KV-cache dtype |
| `enable_chunked_prefill` | bool | `--enable-chunked-prefill` | 이 인스턴스의 스케줄러에서 청크 프리필 활성화 |
| `enable_prefix_caching` | bool | `--enable-prefix-caching` | 이 인스턴스의 로컬 prefix cache 활성화 |
| `prioritize_prefill` | bool | `--prioritize-prefill` | 배치 형성 시 프리필 요청 선호 |
| `enable_local_offloading` | bool | `--enable-local-offloading` | 이 인스턴스에 로컬 offloading을 갖춘 그래프 변환 생성 |
| `enable_attn_offloading` | bool | `--enable-attn-offloading` | 이 인스턴스에 PIM 어텐션 offload 생성 |
| `enable_sub_batch_interleaving` | bool | `--enable-sub-batch-interleaving` | 이 인스턴스의 서브 배치 인터리빙 활성화 |
| `enable_block_copy` | bool | `--enable-block-copy` | 반복되는 transformer 블록에 걸쳐 하나의 블록 트레이스 재사용 |

### `placement` (선택)

레이어별 / 블록별 가중치 + KV-cache 배치 규칙. 작동 예제는 **[예제 → CXL 확장
메모리](/docs/examples/memory-tiers/cxl-memory)**를 참고하세요.

```json
"placement": {
  "default": {"weights": "npu", "kv_loc": "npu", "kv_evict_loc": "cpu"},
  "blocks": [
    {"blocks": "0-3", "weights": "cxl:0", "kv_loc": "npu", "kv_evict_loc": "cpu"}
  ],
  "layers": {
    "embedding": {"weights": "cxl:1", "kv_loc": "npu", "kv_evict_loc": "cpu"}
  }
}
```

| 하위 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `default` | object | ✓ | `blocks`나 `layers`에 없는 레이어 / 블록을 위한 포괄 규칙 |
| `blocks` | array | 선택 | 디코더 블록 범위별 오버라이드 |
| `layers` | object | 선택 | 이름 있는 레이어별 오버라이드 |

각 규칙 객체는 세 개의 문자열 필드를 가집니다:

| 필드 | 허용 값 | 설명 |
| --- | --- | --- |
| `weights` | `npu` / `cpu` / `cxl:<id>` | 이 레이어의 가중치가 있는 곳 |
| `kv_loc` | `npu` / `cpu` / `cxl:<id>` | 활성 KV 블록이 있는 곳(어텐션 레이어만) |
| `kv_evict_loc` | `npu` / `cpu` / `cxl:<id>` | 축출된 KV 블록이 spill되는 곳 |

`blocks` 문자열은 대시와 콤마로 구분된 범위입니다: `"0-3"`, `"4-7"`, `"8,9,10"`,
`"11-23"`. 레이어 이름 키는 아키텍처 YAML의 정식 레이어 이름과 일치해야 합니다.

## 검증 규칙

- `num_nodes == len(nodes)`이고 노드별 `num_instances == len(instances)`.
- 인스턴스별 `weight_per_gpu * num_npus <= npu_mem.mem_size * num_npus`(그렇지 않으면
  시작 시 OOM).
- 하드웨어 폴더가 `profiler/perf/<hardware>/<model_name>/<variant>/tp<tp_size>/`에
  존재해야 함.
- `dp_group`은 유효한 문자열 또는 `null`이어야 함.
- 같은 `dp_group` 내 모든 인스턴스는 같은 `ep_size`와 `tp_size`를 공유해야 함.

## 다음 단계

- **[모델 설정](./model-config)**: `model_name`이 해석되는 파일의 스키마.
- **[PIM 설정](./pim-config)**: `cpu_mem.pim_config`가 해석되는 파일의 스키마.
