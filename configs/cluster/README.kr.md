# configs/cluster

이 디렉터리에는 LLMServingSim의 하드웨어 토폴로지, 인스턴스 레이아웃, 메모리
계층, 인터커넥트 파라미터를 정의하는 클러스터 설정 파일이 있습니다.

`--cluster-config configs/cluster/{name}.json`로 설정 파일을
`python -m serving`에 전달합니다.

## 설정 형식

```json
{
  "num_nodes": 1,
  "link_bw": 16,
  "link_latency": 0,
  "nodes": [
    {
      "num_instances": 1,
      "cpu_mem": {
        "mem_size": 512,
        "mem_bw": 256,
        "mem_latency": 0
      },
      "instances": [
        {
          "model_name": "Qwen/Qwen3-32B",
          "hardware": "RTXPRO6000",
          "npu_mem": {
            "mem_size": 96,
            "mem_bw": 1597,
            "mem_latency": 0
          },
          "num_npus": 2,
          "tp_size": 2,
          "pd_type": null
        }
      ]
    }
  ]
}
```

### 최상위 필드

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `num_nodes` | Integer | 클러스터의 노드 수 |
| `link_bw` | Float 또는 Array<Float> | ASTRA-Sim 토폴로지 링크 대역폭(GB/s). 스칼라는 모든 토폴로지 차원으로 브로드캐스트되며, 배열은 최종 `npus_count` 랭크와 일치해야 함 |
| `link_latency` | Float 또는 Array<Float> | ASTRA-Sim 토폴로지 링크 지연 시간(ns). 스칼라는 모든 토폴로지 차원으로 브로드캐스트되며, 배열은 최종 `npus_count` 랭크와 일치해야 함 |

### 노드별 필드

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `num_instances` | Integer | 이 노드의 인스턴스 수 |
| `cpu_mem.mem_size` | Float | CPU 메모리 용량(GB) |
| `cpu_mem.mem_bw` | Float | CPU 메모리 대역폭(GB/s) |
| `cpu_mem.mem_latency` | Float | CPU 메모리 지연 시간(ns) |

### 인스턴스별 필드

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `model_name` | String | 예 | HuggingFace 모델 식별자 (`configs/model/`와 일치해야 함) |
| `hardware` | String | 예 | `profiler/perf_models/{hardware}/`와 일치하는 하드웨어 이름 |
| `npu_mem` | Object | 예 | NPU 메모리 설정 (`mem_size` GB, `mem_bw` GB/s, `mem_latency` ns) |
| `pd_type` | String/null | 예 | `"prefill"`, `"decode"`, 또는 통합의 경우 `null` |
| `num_npus` | Integer | * | 이 인스턴스의 총 GPU 수 (생략 시 `tp_size * pp_size`에서 유추) |
| `tp_size` | Integer | * | 텐서 병렬 차수 (생략 시 `num_npus // pp_size`에서 유추) |
| `pp_size` | Integer | 아니오 | 파이프라인 병렬 차수 (기본값: 1) |
| `ep_size` | Integer | 아니오 | Expert 병렬 차수 (기본값: MoE는 `tp_size`, dense는 1) |
| `dp_group` | String/null | 아니오 | DP 그룹 ID. 같은 문자열을 가진 인스턴스는 인스턴스 간 ALLTOALL로 expert를 공유 |
| `max_num_seqs` | Integer | 아니오 | `--max-num-seqs`의 인스턴스별 오버라이드 (`0` = 무제한) |
| `max_num_batched_tokens` | Integer | 아니오 | `--max-num-batched-tokens`의 인스턴스별 오버라이드 (`0` = 무제한) |
| `long_prefill_token_threshold` | Integer | 아니오 | `--long-prefill-token-threshold`의 인스턴스별 오버라이드 |
| `block_size` | Integer | 아니오 | `--block-size`의 인스턴스별 오버라이드 |
| `dtype` | String | 아니오 | `--dtype`의 인스턴스별 오버라이드 |
| `kv_cache_dtype` | String | 아니오 | `--kv-cache-dtype`의 인스턴스별 오버라이드 |
| `enable_chunked_prefill` | Boolean | 아니오 | `--enable-chunked-prefill`의 인스턴스별 오버라이드 |
| `enable_prefix_caching` | Boolean | 아니오 | `--enable-prefix-caching`의 인스턴스별 오버라이드 |
| `prioritize_prefill` | Boolean | 아니오 | `--prioritize-prefill`의 인스턴스별 오버라이드 |
| `enable_local_offloading` | Boolean | 아니오 | `--enable-local-offloading`의 인스턴스별 오버라이드 |
| `enable_attn_offloading` | Boolean | 아니오 | `--enable-attn-offloading`의 인스턴스별 오버라이드 |
| `enable_sub_batch_interleaving` | Boolean | 아니오 | `--enable-sub-batch-interleaving`의 인스턴스별 오버라이드 |
| `enable_block_copy` | Boolean | 아니오 | `--enable-block-copy`의 인스턴스별 오버라이드 |

\* `num_npus` 또는 `tp_size` 중 최소 하나는 제공해야 합니다. 나머지는 유추됩니다.

### 인스턴스별 런타임 오버라이드

위에 나열된 13개 런타임 필드(`max_num_seqs`, `max_num_batched_tokens` 등)는
클러스터 설정에서 **인스턴스별 오버라이드**를 지원합니다. 이를 통해 같은
클러스터 내 서로 다른 인스턴스가 서로 다른 스케줄러 제한을 사용하는 이기종
배포가 가능합니다.

**우선순위 규칙:**
```
인스턴스별 값 (클러스터 설정) > 전역 CLI 값 (--flag)
```

각 필드에 대해 런타임은 `instance.get("<field>", args.<field>)`를 읽습니다 —
필드가 클러스터 설정에 있으면 그것이 우선하고, 없으면 전역 CLI 값이 사용됩니다.

**무제한 의미:**
숫자 필드를 `0`으로 설정하면 (`_runtime_limit` 헬퍼를 통해) "무제한"을 의미합니다.
예:
- `max_num_seqs: 0` → 동시 시퀀스 제한 없음
- `max_num_batched_tokens: 0` → 배치 토큰 제한 없음

**검증 게이트:**
- `enable_sub_batch_interleaving: true`는 `enable_attn_offloading: true`를
  요구합니다 (설정 로드 시점에 강제).

**예: 이기종 P/D 인스턴스**

프리필 인스턴스가 `max_num_seqs: 32`(타이트한 동시성)를, 디코드 인스턴스가
`max_num_seqs: 256`(높은 처리량)을 사용하는 구체적인 예는
`single_node_pd_per_instance_config.json`을 참고하세요:

```json
{
  "instances": [
    {
      "pd_type": "prefill",
      "max_num_seqs": 32,
      "max_num_batched_tokens": 8192,
      "enable_chunked_prefill": true
    },
    {
      "pd_type": "decode",
      "max_num_seqs": 256,
      "max_num_batched_tokens": 0,
      "enable_chunked_prefill": false
    }
  ]
}
```

### 병렬화 규칙:
- `num_npus = tp_size * pp_size`
- TP와 EP는 같은 GPU를 공유: 비-MoE 레이어는 TP(ALLREDUCE)를, MoE 레이어는 EP(ALLTOALL)를 사용
- DP는 같은 `dp_group`을 가진 여러 인스턴스로 달성
- `dp_group`이 없으면: `ep_size <= tp_size`
- MoE 모델의 경우: `ep_size`는 `num_local_experts`를 나누어떨어져야 함

### DP+EP 토폴로지:
`dp_group`이 설정되면 `config_builder.py`가 `involved_dim`을 통한 차원별
collective 라우팅을 가진 2D ASTRA-Sim 토폴로지 `[tp_size, dp_group_size]`를
생성합니다. ALLREDUCE(TP)는 dim 0에서만, ALLTOALL(EP)은 dim 1에서 실행됩니다.
DP 그룹의 모든 인스턴스는 wave-synchronized 스케줄링을 통해 하나의 ASTRA-Sim
프로세스를 공유합니다. MoE expert 가중치는 `ep_size`로 샤딩됩니다(각 인스턴스가
`num_local_experts // ep_size`개의 expert를 보유).

### 선택적 필드

| 필드 | 범위 | 타입 | 설명 |
| --- | --- | --- | --- |
| `placement` | instance | Object | 가중치 및 KV cache 위치에 대한 레이어별 배치 규칙 |
| `power` | node | Object | 전력 모델 설정 (NPU idle/standby/active, CPU, DRAM, link, NIC, storage) |
| `cxl_mem` | 최상위 | Object | CXL 메모리 확장 파라미터 (`mem_size`, `mem_bw`, `mem_latency`, `num_devices`) |
| `pim_config` | node cpu_mem | String | `configs/pim/`에 있는 PIM 장치 설정 이름 |

## 제공되는 설정

| 파일 | 설명 |
| --- | --- |
| `single_node_single_instance.json` | 단일 노드, TP=2 Qwen3-32B (기본값) |
| `single_node_single_instance_H100.json` | H100 단일 노드, TP=4 |
| `single_node_multi_instance.json` | 단일 노드, 인스턴스 2개 |
| `single_node_pd_instance.json` | 프리필/디코드 분리(disaggregation)를 갖춘 단일 노드 |
| `single_node_pd_per_instance_config.json` | 프리필/디코드별 런타임 제한을 갖춘 P/D 분리 |
| `single_node_moe_single_instance.json` | 단일 노드, TP=2 EP=2 Qwen3-MoE |
| `single_node_moe_multi_instance.json` | 단일 노드, MoE 인스턴스 2개 |
| `single_node_moe_pd_instance.json` | 단일 노드, P/D 분리를 갖춘 MoE |
| `single_node_cxl_instance.json` | CXL 메모리 확장을 갖춘 단일 노드 |
| `single_node_memory_instance.json` | 가중치/KV 배치 제어를 갖춘 단일 노드 |
| `single_node_pim_instance.json` | PIM 활성화 메모리 + 전력 모델을 갖춘 단일 노드 |
| `single_node_power_instance.json` | 전력 모델링이 활성화된 단일 노드 |
| `dual_node_multi_instance.json` | 노드 2개, 각 노드에 인스턴스 2개 |
| `dual_node_moe_dp_ep_intra_inter_instance.json` | 차원별 intra/inter 링크 설정을 갖춘 2노드 MoE DP+EP 예제 |
