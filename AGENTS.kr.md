# 에이전트.md

이 저장소에서 작업하는 AI 코딩 에이전트(Claude Code, Cursor, Copilot 등)에 대한 지침입니다.

## 프로젝트 컨텍스트

LLMServingSim 2.0은 주기 수준 LLM 서비스 시뮬레이터입니다. Python 프런트엔드를 결합합니다.
ASTRA-Sim(C++ 분석 네트워크 시뮬레이터)을 사용한 (`serving/`, `python -mserving`으로 실행)
백엔드로. 프로파일링 파이프라인(`profiler/`)은 하드웨어별 지연 시간 데이터를 생성합니다.
시뮬레이션을 구동하고 벤치 모듈(`bench/`)은 vLLM을 엔드 투 엔드로 실행합니다.
실제와 비교하여 시뮬레이터를 검증합니다.

### 저장소 구조

```
LLMServingSim/
├── serving/                    # Simulator (`python -m serving`)
│   ├── __main__.py             # Simulation entry point + main loop
│   ├── core/                   # Internals
│   │   ├── scheduler.py        # vLLM-style continuous batching scheduler
│   │   ├── trace_generator.py  # Builds execution traces from profiled latencies
│   │   ├── memory_model.py     # Memory tracking, KV cache, tensor sizes
│   │   ├── graph_generator.py  # Chakra protobuf graph generation
│   │   ├── controller.py       # IPC with ASTRA-Sim subprocess
│   │   ├── router.py           # Request routing across instances
│   │   ├── gate_function.py    # MoE expert token routing
│   │   ├── config_builder.py   # Cluster config → ASTRA-Sim input files
│   │   ├── power_model.py      # Power/energy estimation
│   │   ├── pim_model.py        # PIM device model
│   │   ├── request.py          # Request/Batch data classes
│   │   ├── radix_tree.py       # Prefix cache radix tree (from SGLang)
│   │   ├── logger.py           # Rich-based logger + stdio capture
│   │   └── utils.py            # Model config loading, formatting
│   └── run.sh                  # Example invocations across cluster configs
├── configs/
│   ├── cluster/                # Cluster topology configs (hardware, memory, instances)
│   ├── model/                  # Model architecture configs (subset of HF config.json)
│   └── pim/                    # PIM device configs (DRAMSim3 INI format)
├── workloads/                   # Request trace datasets (.jsonl)
│   └── generators/             # ShareGPT/etc → JSONL workload generators
├── profiler/                   # vLLM-based layerwise profiler (`python -m profiler`)
│   ├── __main__.py             # CLI dispatch (profile / slice)
│   ├── core/                   # internals
│   │   ├── runner.py           # Orchestration (spin_up → categories → spin_down)
│   │   ├── config.py           # Architecture / ProfileArgs / engine defaults
│   │   ├── engine.py           # vLLM lifecycle (tmpdir-based local config load)
│   │   ├── categories.py       # Dense / PerSequence / Attention / Expert
│   │   ├── skew.py             # Heterogeneous-decode skew sweep
│   │   ├── fit_alpha.py        # 5-axis weighted-LS alpha fit
│   │   ├── writer.py           # CSV + meta.yaml writer, TP-stable replication
│   │   ├── logger.py           # Rich-based logger + stdio capture
│   │   └── hooks/              # vLLM-internal-API touchpoints (worker ext, MoE patch, etc.)
│   ├── models/                 # Architecture yamls, one per HF `model_type`
│   ├── power/                  # nvidia-smi / IPMI power-logging helpers
│   ├── perf/                   # Output: perf/<hw>/<model>/<variant>/tp<N>/{dense,per_sequence,attention,moe,skew,skew_fit}.csv
│   ├── v0/                     # Legacy (pre-rewrite) profiler, kept for reference
│   ├── profile.sh              # Editable user template (MODEL / HARDWARE / TP_DEGREES / …)
│   └── profile-all.sh          # Helper: sweeps several MODELs × TP degrees
├── bench/                      # vLLM end-to-end benchmark + sim validation (`python -m bench`)
│   ├── __main__.py             # CLI dispatch (run / validate)
│   ├── core/                   # internals
│   │   ├── runner.py           # AsyncLLM driver, captures RequestStateStats
│   │   ├── recorder.py         # writes meta.json / requests.jsonl / timeseries.csv
│   │   ├── stat_logger.py      # custom vLLM StatLoggerBase that fills timeseries
│   │   ├── validate.py         # bench-vs-sim comparison entry point
│   │   ├── plots.py            # throughput / running-waiting / latency-CDF plot helpers
│   │   └── logger.py           # Rich-based logger + stdio capture
│   ├── results/                # output: bench/results/<run_id>/
│   ├── bench.sh                # host-side wrapper for `python -m bench run`
│   └── validate.sh             # host-side wrapper for `python -m bench validate`
├── scripts/                    # Shared shell entry points (env / build, not module-specific)
│   ├── docker-vllm.sh          # vLLM container (profiler + bench)
│   ├── docker-sim.sh           # simulator container
│   ├── install-vllm.sh         # bare-metal vLLM install (uv venv)
│   └── compile.sh              # ASTRA-Sim + Chakra build
└── astra-sim/                  # ASTRA-Sim C++ backend (submodule)
    ├── inputs/                 # Generated configs (network, memory, system)
    └── extern/graph_frontend/chakra/  # Chakra trace converter
```

논문별 아티팩트 평가 스크립트(이전 `평가/`
디렉토리)는 전용 브랜치(`ispass26-artifact` 등)에 존재하며
주요 가지 트리의 일부가 아닙니다.

### 시뮬레이션 흐름

1. `serving/__main__.py`는 CLI 인수 및 클러스터 구성을 구문 분석합니다.
2. 'config_builder.py'는 ASTRA-Sim 입력 파일(network.yml, system.json, memory_expansion.json)을 생성합니다.
3. ASTRA-Sim 하위 프로세스가 시작됩니다.
4. 반복당:
   - `scheduler.py`는 메모리 및 토큰 예산 제약 하에서 배치를 형성합니다.
   - `trace_generator.py`는 프로파일링된 대기 시간을 조회하고 텍스트 추적을 내보냅니다.
   - `graph_generator.py`는 추적을 Chakra protobuf 그래프로 변환합니다.
   - 'controller.py'는 ASTRA-Sim에 그래프 경로를 제공하고 사이클 수를 다시 읽습니다.
   - `scheduler.py`는 요청 상태를 업데이트하고 완료를 표시합니다.
5. 결과가 인쇄되고 선택적으로 CSV에 저장됩니다.

### 주요 데이터 흐름

```
profile.csv (profiled latencies)
    ↓ _load_perf_db() + _lookup_latency_ns()
trace_generator.py → text trace file
    ↓ Chakra converter
graph_generator.py → .et protobuf file
    ↓ stdin/stdout IPC
ASTRA-Sim (C++) → cycle count
    ↓
scheduler.py → next iteration
```

## 코드 스타일 및 서식

- **Python**: 4칸 들여쓰기, 함수/변수용 snake_case, 클래스용 PascalCase
- **강제 포맷터 없음** — 편집 중인 파일의 주변 코드 스타일과 일치
- **CLI 플래그**: 하이픈 사용(`--cluster-config`, `--max-num-seqs`)
- **내부 Python**: 밑줄 사용(`max_num_seqs`, `enable_chunked_prefill`)
- **JSON 구성 파일 이름**: 설명적인 snake_case(`single_node_pim_instance.json`)
- **가져오기**: 최소화하고 일관성을 유지합니다. `serving/` 모듈은 상대 가져오기를 사용합니다.
- **댓글**: 영어만 사용합니다. 댓글, 독스트링, 로그 메시지에는 한국어 또는 기타 영어가 아닌 텍스트가 없습니다.

## 아키텍처 패턴

### 프로파일러(`profiler/`)
프로파일러는 작업자 확장 클래스를 통해 vLLM에 내장된 `layerwise_profile()`을 사용하여
실제 vLLM 실행 경로에서 레이어별 CUDA 커널 타이밍을 캡처합니다. 건축은
아래의 YAML 카탈로그에 대해 HF 구성의 `model_type` 필드에 의해 전달됩니다.
정규 레이어 이름을 바인딩하는 `profiler/models/<model_type>.yaml`(dense /
시퀀스별/주의/moe)를 vLLM 클래스 이름으로 변경합니다.

모든 TP 수준은 **단일 GPU**에서 프로파일링됩니다. 엔진은 항상 다음을 사용하여 부팅됩니다.
`tensor_parallel_size=1`, 순위별 모양은 `SHARD_FIELDS`를 나누어 에뮬레이트됩니다.
(예: `hidden_size`, `num_attention_heads`) `hf_overrides`를 통해 TP에 의해. 집단
타이밍은 ASTRA-Sim에 달려 있습니다. 모델의 전체 `config.json`(읽기:
`configs/model/<org>/<name>.json` 또는 처음 실행 시 HF Hub에서 자동으로 가져옴)
vLLM은 허브 액세스가 필요하지 않으므로 스핀업 시 tmpdir에 기록됩니다.

속성: 기본 계층별 프로필 방법론(작업자 확장 후크
vLLM의 `layerwise_profile()`, `hf_overrides`를 통한 단일 GPU TP 에뮬레이션)은
[@waneon](https://github.com/waneon)에서 수정되었습니다. 통합된 4D 관심
스윕, `profiler/core/skew.py`의 이종 디코드 스큐 스윕 및
`profiler/core/fit_alpha.py`의 5축 가중치 LS 알파 핏은 다음과 같습니다.
이 저장소에서 개발되었습니다.

각 실행은 카테고리별 CSV 번들을 생성합니다.

```
perf/<hw>/<model>/<variant>/
  meta.yaml                              profiler/vLLM version, effective engine kwargs, GPU,
                                         timestamps, compact sweep specs, skew_fit summary
  tp<N>/
    dense.csv                            layer, tokens, time_us
    per_sequence.csv                     layer, sequences, time_us
    attention.csv                        prefill_chunk, kv_prefill, n_decode, kv_decode, time_us
    moe.csv                              tokens, activated_experts, time_us   (MoE only)
    skew.csv                             raw heterogeneous-decode shots        (skew enabled)
    skew_fit.csv                         fitted per-bucket alpha table         (skew enabled)
```

`<변형>`은 중량 + KV dtype에서 자동 파생됩니다(예: `bf16`, `bf16-kvfp8`,
`--variant`가 설정되지 않은 경우 `fp8-kvfp8`). 시간은 **마이크로초** 단위입니다. 표시된 레이어
yaml(layernorms, 샘플러)의 `tp_stable: true`는 TP=1에서 한 번 프로파일링되고
작성자가 다른 `tp<N>/` 폴더에 복제했습니다.

프로파일러 Docker는 **vLLM v0.19.0**(`vllm/vllm-openai:v0.19.0` 또는
CUDA 13.x의 경우 `v0.19.0-cu130`). MoE 후크는 'FusedMoE.forward_native'를 패치합니다.
강제 전문가 라우팅 — 메서드 이름은 버전에 따라 다릅니다.

### 스큐 프로파일링 및 알파 핏
FlashAttention의 varlen 커널은 타일 패딩 + SM 불균형 비용을 지불합니다.
디코드 배치의 kv 길이가 일정하지 않습니다. 균일한 주의 그리드는 볼 수 없습니다
(모든 샷은 단일 kv_decode 값을 사용합니다) 따라서 `skew.py`는 1초 동안 실행됩니다
바이모달 배치를 스윕하고 사례당 3개의 지연 시간을 측정합니다 — `t_mean`
(모든 배치 평균 디코드), `t_max`(모두 최대값), `t_skew`(
실제 바이모달 혼합). 정규화된 알파 ∈ [0, 1],
`alpha = (t_skew − t_mean) / (t_max − t_mean)`, 시뮬레이터에 얼마나 멀리 있는지 알려줍니다.
평균→최대 선을 따라 치우친 배치가 착륙합니다.

- **스윕 구조**: Tier 1은 `(n, ratio, pc, kp, kvs)`에 대한 계승입니다.
  `_SKEW_REP = 4.0`에서; Tier 2는 소수의 앵커에 스큐 축 스윕을 추가합니다.
  피벗(`skew ∈ {1.5, 2, 4, 8, 16}`). 모든 CLI `SKEW_<축>_FACTOR`
  (기본값 2.0) 해당 축을 기하학적으로 거칠게 만듭니다. 높을수록 빠르며 낮습니다.
  = 더 조밀하다. 요소와 그리드 사양은 `meta.yaml::skew_profile`에 있습니다.
- **맞춤**: `fit_alpha.py`는 5축 키를 기준으로 행을 그룹화합니다.
  `PC | n_라벨 | 왜곡률_라벨 | kv_big_label | kp_label`을 실행하고
  가중 최소제곱은 셀당 적합합니다. 넓어진 부분의 축 절제
  ~13,000개 샘플 데이터 세트는 5축 방식을 선택했습니다(테스트 p50/p90 ≒ 2.7% / 14.8%
  TP=1 대 이전 3축 맞춤의 경우 3.5%/16.4%).
- **데이터 기반 버킷 축**: `n` 및 `kp`는 고유한 버킷당 하나의 버킷을 얻습니다.
  프로파일링된 값(`kp=0` sentinel + 오버플로), `kv_big`은 log-4x bin을 사용합니다.
  관측된 최대값으로 확장된 'skew_rate'는 고정된 정규화 [0, 1]입니다.
  구성표이며 'pc'는 원시 키입니다. 파생 축은 다음 위치에 기록됩니다.
  `meta.yaml::skew_fit.bucket_axes`; 시뮬레이터는 거기에서 그것을 읽습니다
  따라서 프로필 스윕을 넓히면 아무런 문제 없이 더 미세한 해상도가 켜집니다.
  시뮬레이터 코드 변경.
- **스토리지**: 전체(버킷 → 알파) 매핑이 다음으로 유출됩니다.
  `pc, n_label, Skew_rate_label, 열이 있는 `tp<N>/skew_fit.csv`
  kv_big_label, kp_label, 알파, n_samples`. `meta.yaml::skew_fit.per_tp[tp]`
  요약(`method`, `n_samples`, `alpha_default`,
  `rel_err_p50/p90/p99`, `signed_mean`, `bucket_table` 포인터). 이
  Meta.yaml을 ~3100줄에서 변형당 ~100줄로 변환합니다. 는
  시뮬레이터는 `_load_perf_db()`에서 CSV를 메모리로 다시 수화합니다.
- **비활성화**: `SKIP_SKEW=1`은 스윕을 완전히 건너뜁니다(시뮬레이터가 떨어짐).
  풀링된 상수 알파로 돌아갑니다). `ONLY_SKEW=1`은 하나씩 건너뜁니다.
  카테고리를 지정하고 `skew.csv` + `skew_fit.csv`만 새로 고칩니다.

### 주의와 편향으로 공유되는 실현 가능성 범위
균일한 주의 스윕과 스큐 스윕 한도 모두 'n_reqs > max_num_seqs'
(엄격한 `>`, `>=` 아님) `n = MSQ` **순수한** 사례(미리 채우기 청크 없음)에 적합합니다.
이는 vLLM V1의 'input_batch' 버퍼를 정확히 'MSQ'까지 사용합니다. 혼합 사례
`n = MSQ`에는 `MSQ + 1` 요청이 필요하며 여전히 필터링됩니다. 런타임 워크로드인 경우
`n = X`에서 혼합 정권 데이터가 필요하며 `MAX_NUM_SEQS ≥ X + 1`로 프로파일링됩니다.

### 정식 레이어 이름(시뮬레이터 ⇔ 프로파일러, 통합)
시뮬레이터는 프로파일러의 범주별 CSV를 직접 사용합니다. 정식
레이어 이름은 vLLM의 자체 속성 이름과 일치합니다. `trace_generator`는
`profiler/models/<model_type>.yaml`의 `sequence:` 섹션; 아래 표
프로파일러 CSV에서 각 레이어가 나타나는 위치와 시뮬레이터 키가 어떻게 표시되는지 나열합니다.
조회.

| 레이어 | 카테고리(CSV) | 주요 의미 |
|-------|---|---------------|
| '임베딩' | 조밀한 | `토큰 = total_len` |
| `layernorm` | 밀도가 높은(tp_stable) | `토큰 = total_len` |
| `qkv_proj` | 조밀한 | `토큰 = total_len` |
| `qk_norm` | 밀도가 높은(tp_stable, Qwen3에만 해당) | `토큰 = total_len` |
| `rotary_emb` | 조밀한 | `토큰 = total_len` |
| '주의' | 주의 | `(prefill_chunk, kv_prefill, n_decode, kv_decode)` |
| `o_proj` | Dense + ALLREDUCE 이후(TP>1) | `토큰 = total_len` |
| `gate_up_proj` | 조밀한 | `토큰 = total_len` |
| `act_fn` | 조밀한 | `토큰 = total_len` |
| `다운_프로제` | Dense + ALLREDUCE 이후(TP>1) | `토큰 = total_len` |
| `최종층표준` | 밀도가 높은(tp_stable) | `토큰 = total_len` |
| `lm_head` | 시퀀스당 | `시퀀스 = num_requests` |
| `샘플러` | per_sequence(tp_stable) | `시퀀스 = num_requests` |
| '모에' | moe(항상 tp=1에서 프로파일링되고 EP ALLTOALL에 래핑됨) | `(local_tokens, activate_experts)` |

### 추적 생성기 구조
`trace_generator.py`는 아키텍처 yaml의 `sequence:` 섹션을 탐색하여 내보냅니다.
각 반복. 구성 가능한 도우미:
- `resolve_variant()` / `_load_perf_db()` / `_load_architecture()` — 해결
  변형 폴더, Meta.yaml 로드, 카테고리별 CSV 로드, 첨부
  아키텍처 카탈로그 + 시퀀스.
- `_lookup_dense()` / `_lookup_per_sequence()` / `_lookup_attention()` /
  `_lookup_moe()` — 카테고리별 조회. Attention은 4D 조회를 사용합니다.
  (`prefill_chunk, n_decode`의 가장 가까운 이웃, 이중선형
  `kv_prefill, kv_decode`).
- `_emit_sequence()` — yaml에서 표준 이름 목록을 탐색하고 첨부합니다.
  TP ALLREDUCE를 `o_proj`/`down_proj`로 전환하고 PIM 주의를 전환합니다.
  오프로드가 활성화되면 NPU 주의 커널이 활성화되고,
  프로필 CSV에 시퀀스 레이어가 없습니다.
- `_emit_prologue()` / `_emit_pre_attn_layers()` / `_emit_post_attn_layers()` /
  `_emit_final_layers()` — `_emit_sequence`에 대한 얇은 래퍼입니다.
- `_synthesize_interleaved_trace()` — 두 개의 `BatchCtx` 객체를 대체합니다.
  하위 배치 인터리빙.
- `_emit_final_layers()` — final_layernorm → lm_head → 샘플러(샘플러 출력은 REMOTE로 이동)

### 추적 파일 형식
각 추적은 차크라 변환기에서 사용하는 탭으로 구분된 텍스트 파일입니다.

```
COLOCATED		model_parallel_NPU_group: {npu_group}
{num_layers}
Layername    comp_time    input_loc    input_size    weight_loc    weight_size    output_loc    output_size    comm_type    comm_size    misc
embedding_0  5621         REMOTE:0     40            LOCAL         1050673152     LOCAL         81920          NONE         0            NONE
...
sampler_291  25933        LOCAL        2565120       LOCAL         0              REMOTE:0      40             NONE         0            NONE
```

- `comp_time`: 대기 시간(나노초)(profile.csv에서, 로드 시 변환됨)
- `input_loc`/`weight_loc`/`output_loc`: `LOCAL`(NPU), `REMOTE:{node_id}`(CPU), `CXL:{id}`
- `comm_type`: `NONE`, `ALLREDUCE`, `ALLTOALL` 또는 차원 범위 `ALLREDUCE:1,0`, `ALLTOALL:0,1` 사용
  (`:dim0,dim1` 접미사는 다차원 토폴로지를 위한 ASTRA-Sim의 `involved_dim` BoolList에 매핑됩니다.)
- `misc`: `NONE` 또는 하위 배치 인터리빙을 위한 배치 태그(`BATCH_1`, `BATCH_2`)
- 첫 번째 레이어(임베딩) 입력은 'REMOTE'(CPU → NPU)에서 나오고, 마지막 레이어(샘플러) 출력은 'REMOTE'(NPU → CPU)로 이동합니다.
- MoE는 `EXPERT {i}` / `EXPERT END` 마커를 사용합니다(EXPERT 라인의 comm_type은 차원 범위 지정을 포함할 수 있음).
- PIM은 `PIM {channel}` / `PIM END` 마커를 사용합니다.

### 성능DB 및 레이턴시 조회
시뮬레이터는 `_load_perf_db()`를 통해 카테고리별 CSV를 로드하고 디스패치합니다.
카탈로그 카테고리별 조회: `_lookup_dense`(토큰에 대한 1D 선형),
`_lookup_per_sequence`(시퀀스에 대한 1D 선형), `_lookup_attention`(4D:
`(prefill_chunk, n_decode)`에 대한 최근접 이웃 + `(kv_prefill,
kv_decode)`) 및 `_lookup_moe`(`(tokens, activate_experts)`에 대한 2D,
tp=1에서 프로파일링됨). 모든 조회는 추정됩니다(time_us는 선형입니다.
확장) 클램핑 대신. 대기 시간은 마이크로초 단위로 저장됩니다.
CSV로 저장되고 로드 시 나노초로 변환됩니다. 교정 스케일링 없음 —
프로파일링된 대기 시간은 직접 사용됩니다.

기울어짐 수정에 대한 주의: `_lookup_attention_with_skew`는 2개의 4D를 수행합니다.
(`kv_decode_mean` 및 `kv_decode_max`에서) 조회하고 다음을 사용하여 혼합합니다.
`alpha`는 `meta.yaml::skew_fit`에서 `_skew_alpha`에 의해 확인되었습니다. 버킷 키
`pc={pc}|{n_label}|{sr_label}|{kvb_label}|{kp_label}`입니다.
메타의 `skew_fit.bucket_axes`(모듈 기본값으로 대체)
이전 프로필). `_hydrate_skew_fit_tables()`는 각 TP의 `skew_fit.csv`를 읽습니다.
첫 번째 로드 시 메모리 내 'alpha_by_bucket' 맵에 추가됩니다.

프로필 CSV 경로: `profiler/perf/<하드웨어>/<모델>/<변형>/tp<N>/{dense,
per_sequence,attention,moe,skew,skew_fit}.csv`(다음으로 해결됨)
`astra-sim/` 작업 디렉터리의 `../profiler/perf/...`).

변형 해결: `trace_generator.resolve_variant(dtype, kv_cache_dtype,
model_config)`는 프로파일러의 `유효_변형`을 반영합니다. — 가중치 dtype은
CLI 값 또는 모델 구성의 `torch_dtype`(기본값 `bfloat16`),
KV dtype은 'auto'가 아닌 경우 '-kv<short>' 접미사를 추가합니다. 런타임 조회 확인
결과 폴더가 존재합니다. 불일치로 인해 명확한 `FileNotFoundError`가 발생합니다.
누락된 변형을 가리키고 있습니다.

FP8 KV 캐시(`--kv-cache-dtype fp8`)는 `<dtype>-kvfp8` 변형으로 확인됩니다.
폴더(예: `bf16-kvfp8`). `kv_cache_dtype` 매개변수는 다음을 통해 스레드됩니다.
`generate_trace` → `resolve_variant` → `_load_perf_db`. `memory_model.py`에서,
`kv_fp`는 fp8의 경우 1바이트(다른 경우의 `fp`와 비교) KV 캐시 메모리 사용량을 절반으로 줄입니다.

런타임 및 프로파일링된 경고: `(하드웨어, 모델, 변형)`의 첫 번째 로드 시,
시뮬레이터는 CLI의 `--max-num-batched-tokens`와 `--max-num-seqs`를 비교합니다.
`meta.yaml`의 `engine_valid` 값에 대해 일회성 경고를 기록합니다.
런타임이 프로파일러의 스윕 범위를 초과하는 경우(조회가 추정됩니다)

### 에이전트 세션 지원(종속성 체인)
시뮬레이터는 폐쇄 루프 에이전트 워크로드(SWE-벤치, 도구 호출 에이전트)를 지원합니다.
여기서 세션 내의 LLM 호출은 도구 호출과 인터리브된 종속성 체인을 형성합니다.

**데이터세트 형식:** 각 JSONL 줄은 `sub_requests[]`가 포함된 세션입니다. 각 하위 요청
`input_toks`, `output_toks`, `tool_duration_ns`가 있습니다(이 LLM 호출 후 대기 시간은
다음은 시작할 수 있습니다). 플랫 요청('sub_requests' 키 없음)도 역방향으로 지원됩니다.
호환성. 두 형식 모두 동일한 파일에 공존할 수 있습니다.

**라우터 종속성 추적**(`router.py`):
- `load_requests()`는 플랫 형식과 에이전트 형식을 자동으로 감지합니다. 에이전트 세션의 경우
  첫 번째 하위 요청이 대기 중입니다. 나머지는 `_deferred_sessions`에 저장됩니다.
- `notify_request_completed(request_id,complete_time_ns)`는 다음 하위 요청을 해제합니다.
  `completion_time + tool_duration_ns`에 정렬하여 `_pending_requests`에 삽입합니다.
- `has_deferred_sessions()`는 세션이 진행 중인 동안 조기 시뮬레이션 종료를 방지합니다.
- `scheduler.add_request()`는 도착 시간을 유지하기 위해 `bisect.insort`(`append` 아님)를 사용합니다.
  동적으로 해제된 하위 요청이 대기열에 들어갈 때 정렬 순서

**시간 발전:** 모든 인스턴스가 유휴 상태이지만 지연된 하위 요청에 미래가 있는 경우
도착 시간(도구 호출은 여전히 실행 중), `serving/__main__.py`는 `현재`를 다음 보류 시간으로 진행합니다.
바쁜 루핑을 피하기 위해 도착 시간.

### 스케줄러 및 메모리 모델
-`scheduler.py`는 청크 미리 채우기를 사용하여 vLLM 스타일 연속 일괄 처리를 구현합니다(기본값은 켜짐).
- `--max-num-batched-tokens`(기본값 2048) 및 `--max-num-seqs`(기본값 128)로 제어되는 토큰 예산
- `--long-prefill-token-threshold`는 청크 사전 채우기에 대해 단계당 요청당 토큰을 제한합니다.
- KV 캐시는 `--block-size` 토큰 블록으로 관리됩니다(기본값 16).
- RadixAttention을 통한 접두사 캐싱은 기본적으로 활성화됩니다(`--enable-prefix-caching`).
- `memory_model.py`의 메모리 추적은 NPU, CPU 및 CXL 계층을 포괄합니다.
- `calculate_sizes(parallel=)`는 레이어별 텐서 크기를 계산합니다. - `parallel`은 밀도가 높은 경우 TP입니다.
  MoE 전문가를 위한 레이어 및 EP. `head_dim`, `q_dim`, `kv_dim`을 사용합니다.
- MoE 전문가 가중치는 `ep_size`(`tp_size` 아님)로 분할됩니다.
- 프롬프트 처리량(`add_done()`의 `prompt_t`)에는 접두사 캐시 적중 토큰이 포함됩니다.
  실제로 계산된 사전 채우기 토큰이 아닙니다. 이는 vLLM이 보고한 프롬프트와 일치합니다.
  캐시된 토큰을 포함하여 모든 입력 토큰을 계산하는 처리량

### CLI 인수 규칙
CLI 플래그는 해당하는 경우 vLLM 이름을 따릅니다.
- `--dtype` (`float16`, `bfloat16`, `float32`, `int8`) — 모델 가중치 정밀도
- `--skip-prefill` — 사전 채우기 단계를 건너뜁니다(디코드만 해당)
- `--request-routing-policy` (`LOAD`, `RR`, `RAND`, `CUSTOM`) — 인스턴스 간 라우팅을 요청합니다.
- `--expert-routing-policy` (`BALANCED`, `RR`, `RAND`, `CUSTOM`) — MoE를 위한 전문가 토큰 라우팅
  (블록 복사 최적화는 `--enable-block-copy`를 통해 별도로 제어되며 기본값은 켜짐)
- 부울 플래그는 `argparse.BooleanOptionalAction`을 사용합니다(예: `--enable-prefix-caching` /
  `--no-enable-prefix-caching`)

### 머리 치수
일부 모델(예: Qwen3)에는 `head_dim != Hidden_size // num_attention_heads`가 있습니다. 항상 다음을 사용하십시오.
```python
head_dim = config.get('head_dim', n_embd // n_head)
q_dim = n_head * head_dim        # NOT n_embd
kv_dim = kv_head * head_dim      # NOT n_embd // group
```

### 모델 구성
모델 아키텍처 구성은 `configs/model/{org}/{model}.json`에 있습니다. 이들은 하위 집합입니다.
시뮬레이터에 필요한 필드(`hidden_size`,
`num_attention_heads`, `num_hidden_layers`, `num_key_value_heads`, `intermediate_size`,
`vocab_size`, `head_dim`, `num_local_experts`, `num_experts_per_tok`).

시뮬레이터는 `utils.py`의 `get_config(model_name)`을 통해 이를 로드합니다.

### 클러스터 구성
`configs/cluster/`의 클러스터 구성은 하드웨어 토폴로지를 정의합니다. 주요 인스턴스 필드:
- `hardware`: `profiler/perf/<hardware>/`의 디렉터리 이름과 일치해야 합니다.
- `model_name`: `configs/model/{model_name}.json`의 구성과 일치해야 합니다.
- `num_npus`: 인스턴스의 총 GPU(선택 사항, `tp_size * pp_size`에서 추론)
- `tp_size`: 텐서 병렬 정도(필수 또는 추론)
- `pp_size`: 파이프라인 병렬 정도(선택 사항, 기본값 1)
- `ep_size`: 전문가 병렬 수준(선택 사항, MoE의 경우 기본값 `tp_size`, 밀도의 경우 1)
- `dp_group`: DP 그룹 ID 문자열(선택 사항, 동일한 문자열 공유 전문가가 있는 인스턴스)
- `npu_mem.mem_bw`: NPU 메모리 대역폭(system.json에서 `local-mem-bw`로도 설정됨)
- `cpu_mem.mem_bw`: CPU 메모리 대역폭(memory_expansion.json에서 원격 메모리로 설정)
- `link_bw`: 노드 간 대역폭(GB/s)(network.yml에 설정)
- `link_latency`: 노드 간 링크 대기 시간(ns)

병렬성 추론: 사용자가 부분적인 정보를 제공할 수 있습니다(예: `num_npus=4, tp_size=2`)
`config_builder.py`는 나머지(`pp_size=2`)를 추론합니다. 검증을 통해
`num_npus = tp_size * pp_size` 및 `ep_size`는 `num_local_experts`를 나눕니다.

TP와 EP는 동일한 GPU를 공유합니다. 비MoE 레이어는 TP(ALLREDUCE)를 사용하고 MoE 레이어는 EP를 사용합니다.
(전체). DP는 동일한 `dp_group`을 사용하는 여러 인스턴스를 통해 달성됩니다.

`config_builder.py`는 클러스터 구성을 읽고 3개의 ASTRA-Sim 입력 파일을 생성합니다.
-`astra-sim/inputs/network/network.yml` — 토폴로지 및 대역폭
- `astra-sim/inputs/system/system.json` — 예약 정책 및 메모리 대역폭
-`astra-sim/inputs/memory/memory_expansion.json` — 원격(CPU) 메모리 구성

### 작업 디렉토리
`serving/__main__.py`는 실행 초기에 cwd를 `astra-sim/`으로 변경합니다. 시뮬레이터의 모든 상대 경로
repo 루트가 아닌 `astra-sim/`에서 해결하세요. `configs/`, `workloads/`, `profiler/`에 대한 경로
저장소 루트에 상대적이며 코드에서 '../' 접두사가 붙습니다.

### ASTRA-Sim의 통신 크기
ASTRA-Sim은 (NPU별이 아닌) 집합의 **총** 데이터 크기를 예상합니다. N으로 나뉜다
내부적으로(`msg_size = data_size /nodes_in_ring`).
- `o_proj` 및 `down_proj`에 대한 ALLREDUCE: 전체 출력 텐서 크기 전달
- MoE용 ALLTOALL: 전체 활성화 텐서 크기 전달

### 다차원 토폴로지 및 `involved_dim`
DP+EP 구성의 경우 네트워크 토폴로지는 2D: `npus_count: [tp_size, dp_group_size]`입니다.
Collective는 `involved_dim` BoolList 속성을 통해 특정 차원으로 범위가 지정됩니다.
COMM_COLL_NODE protobuf 노드에서:
- ALLREDUCE (TP): `involved_dim=[True, False]` — 희미한 0만
- ALLTOALL(EP): `involved_dim=[False, True]` — 희미한 1만(또는 EP가 TP+DP에 걸쳐 있는 경우 `[True, True]`)

`involved_dim`은 추적 `comm_type` 필드에서 `ALLTOALL:0,1`로 인코딩됩니다(다음으로 구문 분석됨).
차크라 변환기의 `_parse_comm_type`). ASTRA-Sim의 `Workload::issue_comm()`은 다음을 읽습니다.
그리고 이를 `generate_all_to_all()`에 전달합니다. 이는 `involved_dim`이 false인 차원을 건너뜁니다.

`system.json` 집합적 구현에는 토폴로지 차원당 하나의 항목이 있어야 합니다.
(예: 2D의 경우 `"all-to-all-implementation": ["ring", "ring"]`) `config_builder.py`
DP 그룹이 있는지 여부에 따라 자동으로 생성됩니다.

### MoE 전문가 블록
전문가 블록은 ASTRA-Sim에 `EXPERT {i}` / `EXPERT END` 마커를 사용합니다. 각 EP 랭크
로컬 토큰 수를 기반으로 프로파일링된 데이터에서 순위별 대기 시간을 가져오고 활성화됩니다.
전문가(`key_0=local_tokens, key_1=activated_experts`, tp=1에서 프로파일링됨). 순위 실행
ALLTOALL 장벽에서 병렬 및 동기화됩니다. 전문가 대 직급 할당은 짝수를 사용합니다.
파티셔닝: `expert_id * ep_size // num_experts`.

### DP+EP 웨이브 동기화
DP 그룹(동일한 `dp_group`을 가진 인스턴스)의 경우 웨이브 동기화가 이루어집니다.
두 가지 메커니즘을 통해:
1. **Python 측 dp_pending 장벽**: 모든 DP 그룹이 나타날 때까지 추적 생성이 연기됩니다.
   회원들이 배치를 예약했습니다. ALLTOALL `comm_size`는 다음과 동기화됩니다.
   그룹 전체의 `max(total_len) * Hidden_size * fp`.
2. **ASTRA-Sim ALLTOALL 장벽**: 모든 DP 그룹 인스턴스의 `.et` 파일은
   공유 작업 폴더. 두 파일의 ALLTOALL 집합체에 일치하는 스트림이 있습니다.
   ID로 인해 두 NPU가 모두 집합에 도달할 때까지 ASTRA-Sim이 차단됩니다.

하나의 DP 인스턴스가 유휴 상태(요청 없음)이면 더미 배치(디코드 토큰 1개)가 생성됩니다.
ALLTOALL 동기화에 참여할 수 있습니다. 하나의 인스턴스가 모든 요청을 완료하면
모든 DP 그룹 구성원이 완료될 때까지 계속해서 더미 배치를 생성합니다.

### 차크라 그래프 변환기
차크라 변환기(`astra-sim/extern/graph_frontend/chakra/src/converter/llm_converter.py`)
텍스트 추적을 protobuf `.et` 파일로 변환합니다. 다음을 생성합니다.
- 첫 번째 레이어의 입력에 대한 `MEM_LOAD_NODE`(REMOTE/CPU 메모리에서)
- 각 계산 레이어에 대한 `COMP_NODE`
- 마지막 레이어의 출력에 대한 `MEM_STORE_NODE`(REMOTE/CPU 메모리로)
- ALLREDUCE/ALLTOALL에 대한 `COMM_COLL_NODE`(옵션 `involved_dim` BoolList 속성 포함)

변환기는 `_parse_comm_type()`을 통해 `ALLTOALL:0,1`과 같은 `comm_type` 문자열을 구문 분석합니다.
`comm_type="ALLTOALL"` 및 `involved_dim=[False, True]`로 분할됩니다.

MEM_STORE 노드는 **마지막 레이어**의 `output_memory_loc`를 사용합니다. 그렇기 때문에 샘플러는
(lm_head 아님) `output_loc=REMOTE:{node_id}`가 있어야 합니다.

메모리 위치 유형: `LOCAL`(NPU) = 1, `REMOTE`(CPU) = 2, `CXL` = 3, `STORAGE` = 4.
이는 `astra-sim/astra-sim/system/AstraMemoryAPI.hh`의 C++ 열거형과 일치해야 합니다.

### 도커 환경
- **vLLM 컨테이너**(`python -m profiler`, `python -m bench`에서 사용되며
  `python -m Workloads.generators`): `vllm/vllm-openai:v0.19.0`(또는
  CUDA 13.x의 경우 `v0.19.0-cu130`)
  - `scripts/docker-vllm.sh`를 통해 실행됨
  - **LLLMServingSim 저장소 루트**를 `/workspace`로 마운트합니다. 컨테이너 CWD
    는 `/workspace`이므로 `python -m profiler…` 등이 직접 작동합니다.
  - 처음 시작 시 `datasets` 및 `matplotlib` 사전 설치(추가 deps)
    워크로드 생성기 및 벤치 플롯에서 사용됩니다. vLLM이 나머지를 가져옵니다)
  - Gated-config 자동 다운로드를 위해 `scripts/docker-vllm.sh`에서 `HF_TOKEN`을 설정합니다.
- **시뮬레이터 컨테이너**: `astrasim/tutorial-micro2024` + Python deps
  - `scripts/docker-sim.sh`를 통해 실행됨
  - `/app/LLLMServingSim`에 저장소 루트를 마운트합니다. ASTRA-Sim + 차크라는
    처음 사용할 때 `scripts/compile.sh`를 통해 내부에 구축됨

## README 및 문서 분할

저장소에는 의도적인 범위를 가진 두 가지 문서 표면이 있습니다.

- **`README.md`** — 최소한의 현관문. 소개 / 시작하기 / 출판물 /
  인용만 가능합니다. 로고 + 링크바(웹사이트/문서/기여/
  연락처/변경 내역) 다른 모든 내용을 웹사이트에 알려주세요. **하지 마십시오
  세부 콘텐츠(CLI 플래그 테이블, 데이터 세트 스키마, 프로파일러) 다시 추가
  연습, 검증 플롯 등)을 README**에 추가합니다.
  지금 웹사이트.
- **`docs/`** — 공개 문서 사이트(Docusaurus 3, 다음 위치에 배포됨)
  `https://llmservingsim.ai`). 모든 긴 형식의 콘텐츠가 여기에 있습니다. 참조
  사이트별 규칙은 `docs/AGENTS.md`입니다.

사용자에게 표시되는 동작으로 새 기능을 추가하는 경우 이를 문서화하세요.
웹사이트(README 아님).

## 커밋 및 풀 요청 지침

- 짧은 필수 커밋 메시지: `잘못된 evict_size 누적 수정`,
  `Qwen3 모델 지원 추가`
- 커밋에 집중하세요 - 커밋당 하나의 논리적 변경
- 검증에 사용된 정확한 명령을 포함하고 PR에 출력 CSV 경로를 기록해 둡니다.
- 영향을 받는 시뮬레이션 모드와 사용된 구성/데이터 세트를 설명합니다.

## 테스트 및 검증

전용 단위 테스트 스위트가 없습니다. 검증 방법:
1. 가장 작은 관련 `python -mserving…` 시나리오를 실행하고 검사합니다.
   요청별 CSV.
2. 실제 vLLM에 대한 엔드투엔드 정확도 검사를 위해서는 `python -m bench run`을 사용하세요.
   그 뒤에 `python -m bench verify`가 옵니다(`bench/README.md` 참조).
3. 프로파일러 변경: `profiler/profile.sh`에서 `MODEL` / `HARDWARE`를 편집합니다.
   vLLM 컨테이너 내부의 repo 루트에서 `./profiler/profile.sh`를 실행하세요.

## 일반적인 함정

- **변경 사항이 시뮬레이터 통합을 목표로 하지 않는 한`astra-sim/`을 편집하지 마십시오**
  (예: `llm_converter.py`, `Workload.cc`, 입력 구성)
- **대형 파일을 커밋하지 마세요**: 생성된 추적, 출력 CSV, `.et` 파일은 무시됩니다.
- 구성이나 코드에서 **기계별 절대 경로를 사용하지 마세요** — 상대 경로를 사용하세요
  레포에 뿌리를두고
- **요청 속성에 `getattr` 폴백을 추가하지 마세요** — 모든 속성을 초기화하세요.
  `Request.__init__`에서 직접 액세스
- **`hidden_size == num_heads * head_dim`을 가정하지 마세요 — 구성에서 명시적인 `head_dim`을 사용하세요
- **표준 vLLM 레이어 이름 사용**(`qkv_proj`, `o_proj`, `gate_up_proj`,
  `act_fn`, `down_proj`, `rotary_emb`, `qk_norm`, `attention`, `layernorm`,
  `final_layernorm`, `embedding`, `lm_head`, `sampler`, `moe`). 모든 이름은
  시뮬레이터 방출은 아키텍처 yaml의 카탈로그에도 나타나야 합니다.
- **프로파일러 CSV는 마이크로초를 저장합니다**(`time_us` 열) - 시뮬레이터
  1000을 곱하고 로드 시 나노초로 반올림됩니다.
- **첫 번째 및 마지막 추적 레이어는 REMOTE를 사용해야 합니다** - Chakra 변환기는 MEM_LOAD를 생성합니다.
  첫 번째 레이어의 input_loc 노드와 마지막 레이어의 output_loc의 MEM_STORE 노드;
  local_mem이 구성되지 않은 상태에서 둘 중 하나가 LOCAL이면 ASTRA-Sim이 충돌합니다.
- **memory_expansion.json에는 기본적으로 remote_mem만 있습니다** — local_mem은 다음을 제외하면 구성되지 않습니다.
  `--enable-local-offloading`이 사용됩니다. LOCAL의 가중치 부하는 메모리가 아닌 계산 시간을 거칩니다.
- **`config_builder.py`는 실행할 때마다 ASTRA-Sim 입력을 재생성합니다** — 수동으로 편집하지 마세요
  `astra-sim/inputs/` 파일이 지속되기를 기대합니다.
