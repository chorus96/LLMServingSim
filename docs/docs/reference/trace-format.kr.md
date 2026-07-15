---
sidebar_position: 4
title: 트레이스 파일 형식
---

# 트레이스 파일 형식

시뮬레이터의 `trace_generator.py`는 배치별 텍스트 트레이스를 쓰고, Chakra 변환기가
이를 읽어 ASTRA-Sim이 소비하는 `.et` 파일을 생성합니다. 이 페이지는 그 텍스트
트레이스의 **필드별 스펙**입니다.

이 트레이스가 생성되는 *내부 동작*은 **[시뮬레이터 → 트레이스
생성](/docs/simulator/trace-generation)**을 참고하세요.

## 파일 위치

```
astra-sim/inputs/runs/<run_id>/trace/<hardware>/<model>/instance_<i>_batch_<b>.txt
```

run별 ASTRA-Sim 입력 루트 아래에 (인스턴스 × 배치)당 파일 하나. 매 반복 재생성되고
기본적으로 Chakra 변환 후 제거됩니다. 생성된 트레이스를 보존하려면
`--no-cleanup-inputs`를 사용하세요.

## 파일 구조

```
COLOCATED		model_parallel_NPU_group: {npu_group}
{num_layers}
Layername    comp_time    input_loc    input_size    weight_loc    weight_size    output_loc    output_size    comm_type    comm_size    misc
embedding_0    5621    REMOTE:0    40    LOCAL    1050673152    LOCAL    81920    NONE    0    NONE
layernorm_0    1240    LOCAL    81920    LOCAL    8192    LOCAL    81920    NONE    0    NONE
qkv_proj_0    8324    LOCAL    81920    LOCAL    25165824    LOCAL    245760    NONE    0    NONE
...
sampler_291    25933    LOCAL    2565120    LOCAL    0    REMOTE:0    40    NONE    0    NONE
```

### 헤더 (1–3행)

| 행 | 내용 | 의미 |
| --- | --- | --- |
| 1 | `COLOCATED\tmodel_parallel_NPU_group: {npu_group}` | 트레이스 모드 마커. `npu_group`은 이 인스턴스의 NPU ID 콤마 구분 목록 |
| 2 | `{num_layers}` | 뒤따르는 레이어 행의 수 |
| 3 | 열 헤더(탭 구분) | 필드 이름 |

### 레이어 행

각 행은 탭으로 구분된 11개 필드를 가집니다:

| 필드 | 타입 | 의미 |
| --- | --- | --- |
| `Layername` | string | 정식 레이어 이름 + 인덱스(예: `qkv_proj_0`, `attention_31`) |
| `comp_time` | int | **나노초** 단위 계산 지연 시간 |
| `input_loc` | enum | 입력 텐서가 있는 곳([메모리 위치](#memory-locations) 참고) |
| `input_size` | int | 바이트 단위 입력 텐서 크기 |
| `weight_loc` | enum | 레이어 가중치가 있는 곳 |
| `weight_size` | int | 바이트 단위 가중치 크기 |
| `output_loc` | enum | 출력 텐서가 기록될 곳 |
| `output_size` | int | 바이트 단위 출력 텐서 크기 |
| `comm_type` | enum | 이 레이어 이후의 collective 유형([통신](#communication-types) 참고) |
| `comm_size` | int | 바이트 단위 collective 메시지 크기(`comm_type`이 `NONE`이면 `0`) |
| `misc` | string | 기타 태그(서브 배치 인터리빙 등; 보통 `NONE`) |

## 메모리 위치

`input_loc`, `weight_loc`, `output_loc` 필드는 다음 중 하나를 사용합니다:

| 값 | 의미 | 뒷받침 |
| --- | --- | --- |
| `LOCAL` | NPU 메모리 | 인스턴스별 NPU |
| `REMOTE:{node_id}` | 명명된 노드의 CPU 메모리 | 노드별 `cpu_mem` |
| `CXL:{device_id}` | CXL 장치 메모리 | 최상위 `cxl_mem` 블록 |
| `STORAGE` | 스토리지 계층(전력 모델만 사용) | (없음) |

숫자 ID는 `astra-sim/astra-sim/system/AstraMemoryAPI.hh`의 C++ enum과 일치합니다:

| 심볼 | 값 |
| --- | --- |
| `LOCAL` | 1 |
| `REMOTE` | 2 |
| `CXL` | 3 |
| `STORAGE` | 4 |

이들은 트레이스와 C++ enum 사이에서 동기화 상태를 유지해야 합니다; 불일치는 조용한
오집계를 유발합니다.

### 첫 및 마지막 레이어는 REMOTE를 사용해야 함

Chakra 변환기는 **첫** 레이어의 `input_loc`에서 `MEM_LOAD_NODE`를, **마지막**
레이어의 `output_loc`에서 `MEM_STORE_NODE`를 생성합니다. 둘 다 `REMOTE:{node_id}`(CPU
측)여야 합니다: 시뮬레이터는 요청이 NPU에 진입/이탈하는 것을 호스트 측 전송으로
모델링합니다.

그래서 위 예제에서 `embedding_0`이 `input_loc=REMOTE:0`을, `sampler_*`가
`output_loc=REMOTE:0`을 가집니다.

## 통신 유형

`comm_type` 필드는 이 레이어 이후 ASTRA-Sim이 실행하는 collective를 선택합니다:

| 값 | 의미 | 언제 생성 |
| --- | --- | --- |
| `NONE` | collective 없음 | 대부분의 레이어 |
| `ALLREDUCE` | 관련 차원에 걸친 all-reduce | `o_proj`와 `down_proj` 이후(TP > 1) |
| `ALLTOALL` | all-to-all dispatch / combine | MoE 블록 주변(EP 인식) |

### 차원 스코핑

다차원 ASTRA-Sim 토폴로지(DP+EP 레이아웃)의 경우, `comm_type`은 **차원 스코프
접미사**를 포함할 수 있습니다:

| 접미사 | 의미 |
| --- | --- |
| `ALLREDUCE` | 기본, 모든 차원 관련 |
| `ALLREDUCE:1,0` | Dim 0 = 관련(`True`), dim 1 = 아님(`False`). 즉, 2D `[tp, dp]` 토폴로지에서 TP 전용 ALLREDUCE |
| `ALLTOALL:0,1` | Dim 0 = 관련 없음, dim 1 = 관련. 즉, DP 그룹에 걸친 EP 전용 ALLTOALL |

Chakra 변환기는 이를 `_parse_comm_type`으로 파싱하고 `involved_dim` BoolList를
`.et` 파일에 씁니다. ASTRA-Sim의 `Workload::issue_comm()`이 BoolList를 읽어 명명된
차원에서 collective를 라우팅합니다.

## 특수 마커

일부 레이어는 마커로 감싸집니다:

### `EXPERT {i}` / `EXPERT END` (MoE)

랭크별 expert 계산을 감쌈:

```
EXPERT 0
moe_expert_local_3_rank0    1842    LOCAL    524288    LOCAL    9437184    LOCAL    524288    ALLTOALL    524288    NONE
EXPERT END
EXPERT 1
moe_expert_local_3_rank1    1804    LOCAL    524288    LOCAL    9437184    LOCAL    524288    ALLTOALL    524288    NONE
EXPERT END
```

ASTRA-Sim은 각 `EXPERT {i}` 블록을 랭크 `i`에서 병렬로 실행하고, 둘러싼
ALLTOALL에서 동기화합니다.

### `PIM {channel}` / `PIM END` (PIM offload)

PIM 측 어텐션 계산을 감쌈:

```
PIM 0
pim_attention_3    4126    LOCAL    245760    LOCAL    0    LOCAL    245760    NONE    0    NONE
PIM END
```

다중 채널 병렬 어텐션을 모델링하기 위해 여러 `PIM <channel>` 블록이 연속으로 나타날
수 있습니다.

## 서브 배치 인터리빙 (`misc`)

`--enable-sub-batch-interleaving`이 켜지면, 레이어가 `misc`에 배치 태그를 담습니다:

```
qkv_proj_3    4128    ...    NONE    0    BATCH_1
pim_attention_3    8264    ...    NONE    0    BATCH_2
o_proj_3    3845    ...    NONE    0    BATCH_1
```

`BATCH_1`과 `BATCH_2` 절반이 병렬로 실행되며, 보통 한 절반에서 GPU 계산을, 다른
절반에서 PIM 어텐션을 실행합니다.

## 전체 트레이스 예제 (단일 인스턴스, TP=1, dense 모델)

```
COLOCATED		model_parallel_NPU_group: 0
228
Layername	comp_time	input_loc	input_size	weight_loc	weight_size	output_loc	output_size	comm_type	comm_size	misc
embedding_0	5621	REMOTE:0	40	LOCAL	1050673152	LOCAL	81920	NONE	0	NONE
layernorm_0	1240	LOCAL	81920	LOCAL	8192	LOCAL	81920	NONE	0	NONE
qkv_proj_0	8324	LOCAL	81920	LOCAL	25165824	LOCAL	245760	NONE	0	NONE
rotary_emb_0	2104	LOCAL	245760	LOCAL	0	LOCAL	245760	NONE	0	NONE
attention_0	18327	LOCAL	245760	LOCAL	0	LOCAL	81920	NONE	0	NONE
o_proj_0	7452	LOCAL	81920	LOCAL	8388608	LOCAL	81920	NONE	0	NONE
... (디코더 블록 1..31 생략) ...
final_layernorm	1240	LOCAL	81920	LOCAL	8192	LOCAL	81920	NONE	0	NONE
lm_head	28341	LOCAL	81920	LOCAL	1050673152	LOCAL	2565120	NONE	0	NONE
sampler_291	25933	LOCAL	2565120	LOCAL	0	REMOTE:0	40	NONE	0	NONE
```

## Chakra 변환기가 이를 소비하는 방법

Chakra 변환기(`astra-sim/extern/graph_frontend/chakra/src/converter/llm_converter.py`)는
트레이스를 따라가며 Chakra protobuf 노드를 생성합니다:

| 트레이스 행 | Chakra 노드 |
| --- | --- |
| 첫 레이어 | 입력 전송을 위한 `MEM_LOAD_NODE` |
| 각 계산 행 | `comp_time`을 키로 하는 `COMP_NODE` |
| 마지막 레이어 | 출력 전송을 위한 `MEM_STORE_NODE` |
| `comm_type != NONE` | 선택적 `involved_dim` BoolList를 갖춘 `COMM_COLL_NODE` |
| `EXPERT {i}` 블록 | 랭크 `i`에서 실행되는 서브그래프 |
| `PIM <channel>` 블록 | PIM 장치로 라우팅되는 서브그래프 |

`.et` 파일은 `controller.write_flush`가 그다음 ASTRA-Sim에 보내는 것입니다.

## 함정

1. **`comp_time`은 트레이스에서 나노초**이지만 기저의 프로파일 CSV는 마이크로초를
   사용합니다. 변환은 시뮬레이터 시작 시 `_load_perf_db()`에서 일어납니다.
2. **공백이 아니라 탭으로 구분.** 탭과 공백을 섞으면 Chakra 파서가 조용히
   깨집니다.
3. **프로덕션 트레이스를 수동 편집하지 마세요.** 매 반복 재생성됩니다; 수동 편집은
   덮어쓰입니다. 커스텀 타이밍을 주입하려면 프로파일 CSV나 트레이스 생성기를
   수정하세요.
4. **`comm_size`는 랭크별이 아니라 전체 payload입니다.** ASTRA-Sim이 내부적으로 ring
   내 노드 수로 나눕니다.

## 다음 단계

- **[시뮬레이터 → 트레이스 생성](/docs/simulator/trace-generation)** — 각 행이
  어떻게 생성되는지.
- **[클러스터 설정](./cluster-config)**: `placement` 규칙이 `weight_loc`과
  `kv_loc`을 결정.
