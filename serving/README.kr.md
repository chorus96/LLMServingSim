# serving

LLMServingSim 시뮬레이터 코어. `python -m serving --cluster-config <...> [...]`로 실행합니다.

## 레이아웃

```
serving/                        Python 패키지
├── __init__.py                 모듈 맵
├── __main__.py                 시뮬레이션 진입점 + 메인 루프
├── core/                       내부 구현 (아래에 모든 .py 모듈 문서화)
│   ├── scheduler.py            vLLM 스타일 continuous batching 스케줄러
│   ├── trace_generator.py      프로파일된 지연 시간에서 실행 트레이스 생성
│   ├── memory_model.py         메모리 추적, KV cache, 텐서 크기
│   ├── graph_generator.py      Chakra protobuf 그래프 생성
│   ├── controller.py           ASTRA-Sim 서브프로세스와의 IPC
│   ├── router.py               인스턴스 간 요청 라우팅
│   ├── gate_function.py        MoE expert 토큰 라우팅
│   ├── config_builder.py       클러스터 설정 -> ASTRA-Sim 입력 파일
│   ├── power_model.py          전력 / 에너지 추정
│   ├── pim_model.py            PIM 장치 모델
│   ├── request.py              Request / Batch 데이터 클래스
│   ├── radix_tree.py           prefix-cache radix tree (SGLang에서 이식)
│   ├── logger.py               Rich 기반 로거 + stdio 캡처
│   └── utils.py                모델 설정 로딩, 포매팅 헬퍼
└── run.sh                      클러스터 설정별 예제 실행
```

## 아키텍처

`serving/__main__.py`의 시뮬레이션 루프는 반복(iteration)마다 다음 모듈들을 조율합니다:

1. **Router**가 들어오는 요청을 인스턴스로 디스패치
2. **Scheduler**가 메모리 및 토큰 예산 제약 하에 배치를 형성
3. **Trace generator**가 프로파일된 지연 시간을 조회하고 실행 트레이스를 생성
4. **Graph generator**가 트레이스를 Chakra protobuf 그래프로 변환
5. **Controller**가 그래프를 ASTRA-Sim에 공급하고 타이밍 결과를 읽어옴
6. **Memory model**이 KV cache 할당, eviction, prefix cache 히트를 추적

### 트레이스 생성 파이프라인

트레이스 생성기는 아키텍처 yaml(`profiler/models/<model_type>.yaml`)의 순서가
있는 ``sequence:`` 섹션을 따라가며 반복별 실행 트레이스를 구성합니다. 표준
디코더 전용 모델의 경우:

```
prologue (embedding)
  → [pre_attn (layernorm → qkv_proj → [qk_norm] → rotary_emb → attention)
     → post_attn (o_proj[ALLREDUCE] → layernorm)
     → mlp_dense (gate_up_proj → act_fn → down_proj[ALLREDUCE])
        또는 mlp_moe (moe[ALLTOALL])
    ] × N_layers
  → head (final_layernorm → lm_head → sampler)
```

지연 시간은 `profiler/perf/<hardware>/<model>/<variant>/tp<N>/` 아래의
프로파일러 카테고리별 CSV에서 가져옵니다 — `dense.csv`(`tokens` 키),
`per_sequence.csv`(`sequences`), `attention.csv`(`prefill_chunk, kv_prefill,
n_decode, kv_decode`의 4D 그리드), `moe.csv`(`tokens, activated_experts`).
시뮬레이터는 프로파일러가 기록한 폴더와 일치하도록 `--dtype` +
`--kv-cache-dtype`(또는 `--dtype` 생략 시 모델 설정의 `torch_dtype`)에서
`<variant>` 폴더 이름을 결정합니다.

각 variant 옆의 `meta.yaml`은 프로파일러가 스윕한 엔진 플래그(특히
`max_num_batched_tokens`와 `max_num_seqs`)를 기록합니다. 시뮬레이터는 런타임
값이 이를 초과하면 시작 시 경고하여, 조회가 외삽(extrapolate)될 것임을 알립니다.

### Head 차원

일부 모델(예: Qwen3)은 `head_dim != hidden_size // num_attention_heads`입니다.
코드베이스는 항상 모델 설정의 명시적 `head_dim`을 사용합니다:

```python
head_dim = config.get('head_dim', n_embd // n_head)
q_dim = n_head * head_dim        # n_embd 아님
kv_dim = kv_head * head_dim      # n_embd // group 아님
```

### 작업 디렉터리

`serving/__main__.py`는 실행 초기에 cwd를 `astra-sim/`로 변경합니다.
시뮬레이터의 모든 상대 경로는 저장소 루트가 아니라 `astra-sim/`에서
해석됩니다. `configs/`, `workloads/`, `profiler/`로 가는 경로는 코드에서
`../`로 접두됩니다.

## 모듈

아래 모든 모듈은 `serving/core/` 아래에 있습니다. 하위 패키지 내부의 임포트는
상대 형식(`from .X import ...`)을 사용하고, 외부 호출자는
`from serving.core.X import ...`를 사용합니다.

### `request.py`
`Request`와 `Batch` 데이터 클래스를 정의합니다. 요청별 상태와 지연 지표(TTFT,
TPOT, ITL)를 추적합니다.

### `scheduler.py`
vLLM 스타일 continuous batching을 구현하는 인스턴스별 스케줄러입니다. 요청
큐잉, 메모리 제약 배치 형성, KV cache 블록 eviction 및 CPU로의 스왑, prefix
cache 조회를 관리합니다. 커스텀 스케줄링 정책은 여기에 추가하세요.

### `router.py`
현재 시스템 상태를 기반으로 들어오는 요청을 인스턴스 간에 실시간으로
라우팅합니다. 기본 정책 `LOAD`는 vLLM 스타일 가중 최소부하 스코어링(`waiting *
4 + running`)을 사용합니다. 요청은 미리가 아니라 시뮬레이션 루프 중 도착 시각에
라우팅됩니다. Prefill/Decode 분리 모드에서 요청 전송을 처리합니다.

### `gate_function.py`
설정 가능한 정책(Copy, Round Robin, Random, Custom)에 따라 토큰을 MoE expert로
라우팅합니다. `COPY`(기본값)는 block copy 최적화를 활성화합니다. 랭크별 지연
조회를 위한 균등 expert-to-rank 파티셔닝과 함께 `route_ep()`을 통해 EP 인식
라우팅을 제공합니다.

### `memory_model.py`
NPU, CPU, CXL 메모리 사용량을 추적합니다. KV cache 블록 할당과 prefix caching을
위한 RadixCache를 관리합니다. 레이어별 텐서 크기 계산을 위한
`calculate_sizes(parallel=)`와 `get_weight`을 포함합니다. `parallel` 파라미터는
dense 레이어에는 TP 차수, MoE expert에는 EP 차수입니다. MoE expert 가중치는
`ep_size`로 샤딩됩니다. 새 모델 아키텍처를 추가할 때 이들을 수정하세요.

### `radix_tree.py`
prefix cache가 사용하는 토큰 수준 prefix 매칭을 위한 radix tree 자료 구조입니다.
SGLang에서 이식했습니다.

### `trace_generator.py`
핵심 성능 추정기입니다. `profiler/perf/<hardware>/<model>/<variant>/tp<N>/`
아래의 프로파일러 카테고리별 CSV와 아키텍처 yaml
(`profiler/models/<model_type>.yaml`)을 로드하고, yaml의 ``sequence:`` 섹션을
따라가며 각 반복의 레이어를 생성합니다. 조합 가능한 헬퍼:

- `resolve_variant()` / `_load_perf_db()` / `_load_architecture()` —
  `(hardware, model, dtype, kv_cache_dtype)`를 카테고리 테이블과 시퀀스 순서를
  가진 로드된 DB로 변환.
- `_lookup_dense()` / `_lookup_per_sequence()` / `_lookup_attention()` /
  `_lookup_moe()` — 카테고리별 조회. 1D 선형 보간(dense/per_sequence),
  attention에는 (prefill_chunk, n_decode)에 대한 4D 최근접이웃 + (kv_prefill,
  kv_decode)에 대한 bilinear, MoE에는 2D.
- `_lookup_attention_with_skew()` / `_skew_alpha()` — attention 커널의 skew
  보정: 두 번의 4D 조회(배치의 평균 및 최대 decode kv에서)를
  `meta.yaml::skew_fit`에서 결정된 버킷별 alpha로 블렌딩. 버킷 축(`n`,
  `skew_rate`, `kv_big`, `kp`; `pc`는 원본 사용)은 meta에서 읽으므로,
  시뮬레이터가 프로파일러가 최종적으로 얻은 해상도가 무엇이든 자동으로
  가져옴. meta가 skew_fit 블록보다 오래된 경우 pooled fallback 상수를 사용 —
  시뮬레이터는 오래된 프로파일 실행에 대해서도 사용 가능한 상태 유지.
- `_hydrate_skew_fit_tables()` — 로드 시, 각 TP의 `bucket_table:` 포인터를
  따라가 `tp<N>/skew_fit.csv`를 `_skew_alpha`가 참조하는 인메모리
  `alpha_by_bucket` 맵으로 읽어들임.
- `TraceCtx` / `BatchCtx` / `PowerAccumulator` — 컨텍스트 전달을 위한 데이터 클래스
- `_emit_layer()` — 카탈로그 카테고리별로 디스패치하는 단일 레이어 생성
- `_emit_sequence()` — yaml의 정식 이름 리스트를 따라감. `o_proj`/`down_proj`에
  TP ALLREDUCE를 부착하고, offloading이 활성화되면 NPU attention 커널 앞에 PIM
  attention을 삽입. 시퀀스 레이어가 프로파일 CSV에 없으면 일회성 경고를 발생.
- `_emit_prologue()` / `_emit_pre_attn_layers()` / `_emit_post_attn_layers()` /
  `_emit_final_layers()` — `_emit_sequence`에 대한 섹션별 래퍼.
- `_synthesize_interleaved_trace()` — 서브 배치 인터리빙을 위해 두 개의
  `BatchCtx` 객체를 번갈아 사용.

텐서 병렬화(ALLREDUCE 배치), DP+EP를 위한 `involved_dim` 차원 스코핑을 갖춘
MoE expert 라우팅, PIM attention offloading, 서브 배치 인터리빙을 처리합니다.
`comm_type` 필드는 다차원 ASTRA-Sim 토폴로지를 위한 차원 스코핑(예:
`ALLTOALL:0,1`)을 지원합니다. 새 모델 아키텍처를 추가하려면 이 파일을 편집하는
대신 일치하는 `sequence:`를 가진 `profiler/models/<model_type>.yaml`을
추가하세요.

### `config_builder.py`
`configs/cluster/`의 사용자 제공 클러스터 설정 JSON을 파싱하고
`astra-sim/inputs/runs/<run_id>/` 아래에 ASTRA-Sim 입력 파일을 생성합니다:
`network/network.yml`, `memory/memory_expansion.json`, `system/system.json`.
반복별 텍스트 트레이스는 기본적으로 Chakra 변환 후 제거되고, 생성된 run
디렉터리는 기본적으로 시뮬레이션 성공 후 제거됩니다. 디버깅을 위해 트레이스,
Chakra 워크로드, 입력 설정을 보존하려면 `--no-cleanup-inputs`를 사용하세요.
DP 그룹의 경우 2D 네트워크 토폴로지 `[tp_size, dp_group_size]`를 생성하고,
`system.json`의 collective 구현을 토폴로지 차원 수에 맞게 설정합니다.
`involved_dim` 스코핑을 위해 인스턴스별 `tp_dim`/`ep_dim`을 계산합니다.

### `power_model.py`
NPU, CPU, DRAM, 인터커넥트, NIC, 스토리지를 포함하여 노드별 전력 및 에너지
소비를 추정합니다.

### `controller.py`
ASTRA-Sim 서브프로세스와의 IPC 프로토콜을 관리합니다. 워크로드 그래프 경로를
ASTRA-Sim stdin에 쓰고, stdout에서 반복 타이밍을 파싱합니다.

### `graph_generator.py`
Chakra 변환기를 호출하여 텍스트 형식 실행 트레이스를 ASTRA-Sim이 소비하는
protobuf 워크로드 그래프로 변환합니다.

### `pim_model.py`
`configs/pim/`의 PIM 장치 INI 설정 파일을 파싱합니다. 트레이스 생성기가
PIM-offloaded attention에 사용하는 대역폭, 지연 시간, 전력 파라미터를 유도합니다.

### `utils.py`
모델 설정 로딩, 워크로드 경로 구성, 터미널 출력 포매팅을 위한 헬퍼 함수입니다.

### `logger.py`
LLMServingSim 로거를 구성합니다. 로그 레벨은 `python -m serving` CLI의
`--log-level`로 설정합니다.
