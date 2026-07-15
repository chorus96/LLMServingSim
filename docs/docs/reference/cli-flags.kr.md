---
sidebar_position: 1
title: CLI 플래그
---

# `python -m serving` CLI 플래그

`python -m serving`이 받는 모든 명령줄 플래그의 완전한 레퍼런스입니다. 각 플래그의
개념적 측면(내부적으로 무엇을 *하는지*)은
**[시뮬레이터](/docs/simulator/architecture)**를 참고하세요.

## 클러스터 토폴로지

| 플래그 | 타입 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `--cluster-config` | path | `configs/cluster/single_node_single_instance.json` | 클러스터 설정 JSON 경로. **[클러스터 설정](./cluster-config)** 참고 |
| `--network-backend` | choice | `analytical` | 네트워크 시뮬레이션 백엔드. `analytical`(빠름) 또는 `ns3`(상세, WIP) |

## 배치 및 스케줄링

이 플래그들은 배포 기본값입니다. 클러스터 설정이 `instances[i]`별로 일치하는 런타임
노브를 오버라이드할 수 있습니다;
**[클러스터 설정](./cluster-config#runtime-overrides-optional)** 참고.

| 플래그 | 타입 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `--max-num-seqs` | int | `128` | 배치의 최대 시퀀스 수. `0` = 무제한 |
| `--max-num-batched-tokens` | int | `2048` | 모든 요청에 걸친 반복당 최대 토큰(토큰 예산) |
| `--long-prefill-token-threshold` | int | `0` | 청크 프리필의 스텝당 요청별 토큰 상한. `0` = 비활성화 |
| `--enable-chunked-prefill` | bool | `True` | 긴 프리필을 반복에 걸쳐 분할. 비활성화하려면 `--no-enable-chunked-prefill` 사용 |
| `--prioritize-prefill` | flag | off | 같은 반복에서 디코드보다 프리필을 먼저 실행 |
| `--block-size` | int | `16` | KV cache 블록 크기(토큰) |
| `--skip-prefill` | flag | off | 프리필을 건너뛰고 디코드만 실행 |

## 라우팅

| 플래그 | 선택지 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `--request-routing-policy` | `LOAD` / `RR` / `RAND` / `CUSTOM` | `LOAD` | 인스턴스 간 요청 라우팅 |
| `--expert-routing-policy` | `BALANCED` / `RR` / `RAND` / `CUSTOM` | `BALANCED` | MoE expert 토큰 라우팅 |
| `--enable-block-copy` | bool | `True` | 하나의 블록 트레이스를 레이어에 걸쳐 재생(레이어별 EP 분산을 위해 False 설정) |

## 정밀도

| 플래그 | 선택지 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `--dtype` | `float16` / `bfloat16` / `float32` / `fp8` / `int8` | 모델의 `torch_dtype`, 폴백 `bfloat16` | 모델 가중치 dtype |
| `--kv-cache-dtype` | `auto` / `fp8` | `auto`(dtype 상속) | KV cache dtype. `fp8`은 KV 메모리를 절반으로 하고 `*-kvfp8` 프로파일 variant를 선택 |

## Prefix caching과 offloading

| 플래그 | 기본값 | 설명 |
| --- | --- | --- |
| `--enable-prefix-caching` | `True` | RadixAttention prefix caching. 비활성화하려면 `--no-enable-prefix-caching` 사용 |
| `--enable-prefix-sharing` | off | 노드 내 인스턴스 간에 공유되는 2차 계층 prefix pool |
| `--prefix-storage` | `None` | 2차 계층 pool의 위치. `None` / `CPU` / `CXL` |
| `--enable-local-offloading` | off | NPU로의 가중치 offloading(프로파일링에서 가중치 읽기 계수) |
| `--enable-attn-offloading` | off | PIM으로의 어텐션 계산 offloading |
| `--enable-sub-batch-interleaving` | off | GPU 계산을 PIM 어텐션과 오버랩. `--enable-attn-offloading` 필요 |
| `--sparse-attention-ratio` | `None` | NELSSA dynamic sparse attention: 디코드 스텝당 유지하는 KV 토큰 비율(예: `0.02`). `--enable-attn-offloading` 필요 |
| `--sparse-vector-search-nprobe` | `32` | NELSSA 토큰 선택(vector search) 중 탐색하는 IVF 리스트 수 |
| `--attention-local-window` | `0` | NELSSA GPU-local KV 분할: GPU HBM에 유지하고 GPU에서 어텐션하는 최근 디코드 토큰, PIM 벌크 어텐션과 오버랩. `--enable-attn-offloading` 필요 |
| `--attention-sink-tokens` | `0` | NELSSA GPU-local KV 분할: GPU HBM에 유지하는 선두 attention-sink 토큰(local window에 추가). `--enable-attn-offloading` 필요 |
| `--sparse-index-build` / `--no-sparse-index-build` | on | 프리필 시 RetrievalAttention vector-index 빌드 비용을 모델링(레이어별, PNM 모듈에서). `--sparse-attention-ratio`가 설정된 경우에만 적용 |
| `--sparse-index-footprint-ratio` | `0.10` | KV cache 대비 비율로서의 RetrievalAttention vector-index 메모리 풋프린트(PNM에 저장, 유효 KV 용량 감소). `0`은 비활성화. Sparse 모드 전용 |
| `--pnm-combine-comm` / `--no-pnm-combine-comm` | on | 디코드 어텐션 combine 전송을 모델링: query를 PNM으로 내려보내고 부분 결과를 인터커넥트(`link_bw`)로 읽어옴. `--enable-attn-offloading` 필요 |
| `--pnm-kv-seq-partition` / `--no-pnm-kv-seq-partition` | off | NELSSA multi-module: 각 디코드 요청의 KV 시퀀스를 모든 PNM 유닛에 파티션하여 단일 요청이 모든 모듈을 사용(단일 요청 병렬성을 `kv_head` 너머로 해제). `--enable-attn-offloading` 필요 |
| `--pnm-modules` | `1` | PNM 모듈 수; combine 인터커넥트 대역폭을 스케일(모듈별 링크) |
| `--hermes-hot-ratio` | `None` | Hermes 베이스라인: GPU HBM에 hot으로 유지하는 FFN 뉴런 비율. GPU가 hot 비율을 계산; 활성화된 cold 뉴런은 DIMM/PNM에서 near-data로 스트리밍되어 GPU FFN과 오버랩되므로 숨겨지지 않은 DIMM residual만 스텝을 연장. `--enable-attn-offloading` 필요 |
| `--hermes-cold-activation` | `0.1` | Hermes: DIMM에서 near-data로 스트리밍되는 토큰당 활성화된 cold FFN 뉴런 비율(contextual sparsity). `--hermes-hot-ratio`가 설정된 경우에만 적용 |
| `--flexgen-host-offload` | off | FlexGen 베이스라인: KV cache를 host DRAM에 두고 GPU에서 어텐션을 계산하며, 매 디코드 스텝마다 어텐션되는 KV를 인터커넥트(`link_bw`)로 스트리밍. Transfer-bound(near-memory 계산 없음, sparsity 없음) — PNM 경로와의 host-offload 대조. `--enable-attn-offloading`과 상호 배타 |
| `--infinigen-prefetch-ratio` | `None` | InfiniGen 베이스라인: KV cache를 host DRAM에 두되, 매 디코드 스텝마다 이 비율의 KV 토큰(예: `0.02`)만 GPU로 speculative하게 프리페치하고 그에 대해 어텐션을 계산. speculation scan + *선택된* KV의 `link_bw` 전송 비용을 지불 — FlexGen(전부 전송)과 PNM(전송 없음)의 중간. `--enable-attn-offloading` / `--flexgen-host-offload`와 상호 배타 |
| `--infinigen-speculation-ratio` | `0.25` | InfiniGen: 전체 KV GPU 어텐션 대비 비율로서의 partial-attention speculation scan 비용(partial rank / head_dim). `--infinigen-prefetch-ratio`와 함께만 적용 |
| `--retrieval-cpu-sparse` | off | RetrievalAttention-CPU 베이스라인: NELSSA와 동일한 dynamic sparse attention(IVF 선택 + index 빌드)을 실행하되 PNM 대신 CPU 코어에서 — 채널별 near-memory 병렬성을 잃어 디코드 어텐션이 CPU-bound. `--enable-attn-offloading`과 `--sparse-attention-ratio` 필요 |
| `--retrieval-cpu-parallel` | `1` | RetrievalAttention-CPU: sparse attention을 위한 병렬 CPU 계산 스트림 수(디코드 요청이 그 사이에 분배됨; `1` = 직렬). `--retrieval-cpu-sparse`와 함께만 적용 |

## 데이터셋과 출력

| 플래그 | 타입 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `--dataset` | path | `None` | JSONL 워크로드 파일. **[워크로드 → JSONL 형식](/docs/workloads/jsonl-format)** 참고 |
| `--num-reqs` | int | `0` | 데이터셋에서 로드할 항목 수(`0` = 전부). agentic의 경우 각 항목이 세션 |
| `--output` | path | `None` | 요청별 CSV 출력 경로. `None`이면 stdout만. 리터럴 `{run_id}`는 활성 run id로 대체됨 |

## Run 격리

각 호출은 병렬 시뮬레이션이 서로의 생성된 설정, 트레이스, Chakra 워크로드를
덮어쓰지 않도록 run별 입력 루트 아래에 ASTRA-Sim 중간 파일을 씁니다. 생성된 텍스트
트레이스는 기본적으로 Chakra 변환 후 제거되고, run별 입력 루트는 기본적으로
시뮬레이션 성공 후 제거됩니다.

| 플래그 | 타입 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `--run-id` | string | 자동 생성 | 이 시뮬레이션 run의 경로 안전 id. `astra-sim/inputs/runs/<run-id>`와 `{run_id}` 출력 자리 표시자에 사용 |
| `--inputs-root` | path | `astra-sim/inputs/runs/<run-id>` | 생성된 ASTRA-Sim 입력 루트를 오버라이드, 예를 들어 중간 파일을 로컬 SSD나 tmpfs에 두기 위해 |
| `--cleanup-inputs` / `--no-cleanup-inputs` | bool | `true` | Chakra 변환 후 생성된 트레이스 파일을 제거하고 시뮬레이션 성공 후 생성된 run 디렉터리를 제거. 디버깅을 위해 트레이스, Chakra 워크로드, 입력 설정을 보존하려면 `--no-cleanup-inputs` 사용 |

## 로깅

| 플래그 | 타입 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `--log-interval` | float | `1.0` | throughput / 메모리 로그 라인 사이의 초 |
| `--log-level` | choice | `WARNING` | `WARNING`(기본) / `INFO` / `DEBUG` |

## 빠른 참조: 어떤 기능에 어떤 플래그

| 기능 | 플래그 |
| --- | --- |
| 다중 인스턴스(클러스터 설정을 통한 병렬화) | (클러스터 설정 `num_instances`) |
| 텐서 병렬 | (클러스터 설정 `tp_size`) |
| MoE expert 병렬 | (클러스터 설정 `ep_size`) |
| DP+EP MoE | (클러스터 설정 `dp_group`) |
| Prefix caching | `--enable-prefix-caching`(기본 켜짐), `--enable-prefix-sharing`, `--prefix-storage` |
| 청크 프리필 | `--enable-chunked-prefill`(기본 켜짐), `--long-prefill-token-threshold` |
| PIM 어텐션 offload | `--enable-attn-offloading`(클러스터 설정이 `pim_config` 설정) |
| FP8 KV cache | `--kv-cache-dtype fp8` |
| ns3 백엔드 | `--network-backend ns3` |

각 기능의 완전한 개념적 설명은 **[시뮬레이터](/docs/simulator/architecture)**
섹션을 둘러보세요. 실행 가능한 예제는 **[예제](/docs/examples)**를 참고하세요.
