# AGENTS.md

이 저장소에서 작업하는 AI 코딩 에이전트(Claude Code, Cursor, Copilot 등)를 위한 가이드라인입니다.

## 프로젝트 맥락

LLMServingSim 2.0은 사이클 수준(cycle-level) LLM 서빙 시뮬레이터입니다. Python
프런트엔드(`serving/`, `python -m serving`으로 실행)와 백엔드인 ASTRA-Sim(C++
analytical 네트워크 시뮬레이터)을 결합합니다. 프로파일링 파이프라인(`profiler/`)이
시뮬레이션을 구동하는 하드웨어별 지연 시간 데이터를 생성하고, bench 모듈(`bench/`)이
vLLM을 end-to-end로 실행하여 시뮬레이터를 ground truth와 대조 검증합니다.

### 저장소 구조

```
LLMServingSim/
├── serving/                    # 시뮬레이터 (`python -m serving`)
│   ├── __main__.py             # 시뮬레이션 진입점 + 메인 루프
│   ├── core/                   # 내부 구현
│   │   ├── scheduler.py        # vLLM 스타일 continuous batching 스케줄러
│   │   ├── trace_generator.py  # 프로파일된 지연 시간에서 실행 트레이스 생성
│   │   ├── memory_model.py     # 메모리 추적, KV cache, 텐서 크기
│   │   ├── graph_generator.py  # Chakra protobuf 그래프 생성
│   │   ├── controller.py       # ASTRA-Sim 서브프로세스와의 IPC
│   │   ├── router.py           # 인스턴스 간 요청 라우팅
│   │   ├── gate_function.py    # MoE expert 토큰 라우팅
│   │   ├── config_builder.py   # 클러스터 설정 → ASTRA-Sim 입력 파일
│   │   ├── power_model.py      # 전력/에너지 추정
│   │   ├── pim_model.py        # PIM 장치 모델
│   │   ├── request.py          # Request/Batch 데이터 클래스
│   │   ├── radix_tree.py       # Prefix cache radix tree (SGLang에서)
│   │   ├── logger.py           # Rich 기반 로거 + stdio 캡처
│   │   └── utils.py            # 모델 설정 로딩, 포매팅
│   └── run.sh                  # 클러스터 설정별 예제 실행
├── configs/
│   ├── cluster/                # 클러스터 토폴로지 설정 (하드웨어, 메모리, 인스턴스)
│   ├── model/                  # 모델 아키텍처 설정 (HF config.json의 부분집합)
│   └── pim/                    # PIM 장치 설정 (DRAMSim3 INI 형식)
├── workloads/                   # 요청 트레이스 데이터셋 (.jsonl)
│   └── generators/             # ShareGPT/등 → JSONL 워크로드 생성기
├── profiler/                   # vLLM 기반 레이어별 프로파일러 (`python -m profiler`)
│   ├── __main__.py             # CLI 디스패치 (profile / slice)
│   ├── core/                   # 내부 구현
│   │   ├── runner.py           # 오케스트레이션 (spin_up → categories → spin_down)
│   │   ├── config.py           # Architecture / ProfileArgs / 엔진 기본값
│   │   ├── engine.py           # vLLM 생명주기 (tmpdir 기반 로컬 설정 로드)
│   │   ├── categories.py       # Dense / PerSequence / Attention / Expert
│   │   ├── skew.py             # 이기종 디코드 skew 스윕
│   │   ├── fit_alpha.py        # 5축 weighted-LS alpha 피팅
│   │   ├── writer.py           # CSV + meta.yaml writer, TP-stable 복제
│   │   ├── logger.py           # Rich 기반 로거 + stdio 캡처
│   │   └── hooks/              # vLLM 내부 API 접점 (worker ext, MoE patch 등)
│   ├── models/                 # 아키텍처 yaml, HF `model_type`당 하나
│   ├── power/                  # nvidia-smi / IPMI 전력 로깅 헬퍼
│   ├── perf/                   # 출력: perf/<hw>/<model>/<variant>/tp<N>/{dense,per_sequence,attention,moe,skew,skew_fit}.csv
│   ├── v0/                     # 레거시(재작성 이전) 프로파일러, 참조용 보존
│   ├── profile.sh              # 편집 가능한 사용자 템플릿 (MODEL / HARDWARE / TP_DEGREES / …)
│   └── profile-all.sh          # 헬퍼: 여러 MODEL × TP 차수 스윕
├── bench/                      # vLLM end-to-end 벤치마크 + sim 검증 (`python -m bench`)
│   ├── __main__.py             # CLI 디스패치 (run / validate)
│   ├── core/                   # 내부 구현
│   │   ├── runner.py           # AsyncLLM 드라이버, RequestStateStats 캡처
│   │   ├── recorder.py         # meta.json / requests.jsonl / timeseries.csv 기록
│   │   ├── stat_logger.py      # timeseries를 채우는 커스텀 vLLM StatLoggerBase
│   │   ├── validate.py         # bench-vs-sim 비교 진입점
│   │   ├── plots.py            # throughput / running-waiting / latency-CDF 플롯 헬퍼
│   │   └── logger.py           # Rich 기반 로거 + stdio 캡처
│   ├── results/                # 출력: bench/results/<run_id>/
│   ├── bench.sh                # `python -m bench run`의 호스트 측 래퍼
│   └── validate.sh             # `python -m bench validate`의 호스트 측 래퍼
├── scripts/                    # 공유 셸 진입점 (환경 / 빌드, 모듈 전용 아님)
│   ├── docker-vllm.sh          # vLLM 컨테이너 (profiler + bench)
│   ├── docker-sim.sh           # 시뮬레이터 컨테이너
│   ├── install-vllm.sh         # 베어메탈 vLLM 설치 (uv venv)
│   └── compile.sh              # ASTRA-Sim + Chakra 빌드
└── astra-sim/                  # ASTRA-Sim C++ 백엔드 (서브모듈)
    ├── inputs/                 # 생성된 설정 (network, memory, system)
    └── extern/graph_frontend/chakra/  # Chakra 트레이스 변환기
```

논문별 artifact 평가 스크립트(이전 `evaluation/` 디렉터리)는 전용
브랜치(`ispass26-artifact` 등)에 있으며 main 브랜치 트리의 일부가 아닙니다.

### 시뮬레이션 흐름

1. `serving/__main__.py`가 CLI 인자와 클러스터 설정을 파싱
2. `config_builder.py`가 ASTRA-Sim 입력 파일 생성(network.yml, system.json, memory_expansion.json)
3. ASTRA-Sim 서브프로세스 실행
4. 반복마다:
   - `scheduler.py`가 메모리 및 토큰 예산 제약 하에 배치를 형성
   - `trace_generator.py`가 프로파일된 지연 시간을 조회하고 텍스트 트레이스를 생성
   - `graph_generator.py`가 트레이스를 Chakra protobuf 그래프로 변환
   - `controller.py`가 그래프 경로를 ASTRA-Sim에 공급하고 사이클 수를 읽어옴
   - `scheduler.py`가 요청 상태를 갱신하고 완료를 표시
5. 결과가 출력되고 선택적으로 CSV에 저장됨

### 핵심 데이터 흐름

```
profile.csv (프로파일된 지연 시간)
    ↓ _load_perf_db() + _lookup_latency_ns()
trace_generator.py → 텍스트 트레이스 파일
    ↓ Chakra 변환기
graph_generator.py → .et protobuf 파일
    ↓ stdin/stdout IPC
ASTRA-Sim (C++) → 사이클 수
    ↓
scheduler.py → 다음 반복
```

## 코드 스타일 & 포매팅

- **Python**: 4칸 들여쓰기, 함수/변수는 snake_case, 클래스는 PascalCase
- **강제 포매터 없음** — 편집 중인 파일의 주변 코드 스타일과 일치시킬 것
- **CLI 플래그**: 하이픈 사용 (`--cluster-config`, `--max-num-seqs`)
- **내부 Python**: 언더스코어 사용 (`max_num_seqs`, `enable_chunked_prefill`)
- **JSON 설정 파일 이름**: 서술적 snake_case (`single_node_pim_instance.json`)
- **임포트**: 최소하고 일관되게 유지; `serving/` 모듈은 상대 임포트 사용
- **주석**: 영어만 사용 — 주석, docstring, 로그 메시지에 한국어나 기타 비영어 텍스트 금지

## 아키텍처 패턴

### 프로파일러 (`profiler/`)
프로파일러는 worker extension 클래스를 통해 vLLM 내장 `layerwise_profile()`을
사용하여 실제 vLLM 실행 경로에서 레이어별 CUDA 커널 타이밍을 캡처합니다.
아키텍처는 HF 설정의 `model_type` 필드로 `profiler/models/<model_type>.yaml`
아래의 YAML 카탈로그에 디스패치되며, 이 카탈로그는 정식 레이어 이름(dense /
per-sequence / attention / moe)을 vLLM 클래스 이름에 바인딩합니다.

모든 TP 차수는 **단일 GPU**에서 프로파일됩니다: 엔진은 항상
`tensor_parallel_size=1`로 부팅되며, 랭크별 형상은 `hf_overrides`를 통해
`SHARD_FIELDS`(예: `hidden_size`, `num_attention_heads`)를 TP로 나누어
에뮬레이션됩니다. Collective 타이밍은 ASTRA-Sim에 맡깁니다. 모델의 전체
`config.json`(`configs/model/<org>/<name>.json`에서 읽거나 최초 실행 시 HF Hub에서
자동 fetch)은 spin-up 시 tmpdir에 기록되므로 vLLM은 Hub 접근이 결코 필요 없습니다.

출처(Attribution): 기본 레이어별 프로파일 방법론(vLLM의 `layerwise_profile()`에
대한 worker-extension 훅, `hf_overrides`를 통한 단일 GPU TP 에뮬레이션)은
[@waneon](https://github.com/waneon)에서 차용했습니다. 통합 4D 어텐션 스윕,
`profiler/core/skew.py`의 이기종 디코드 skew 스윕, `profiler/core/fit_alpha.py`의
5축 weighted-LS alpha 피팅은 이 저장소에서 개발되었습니다.

각 실행은 카테고리별 CSV 번들을 생성합니다:

```
perf/<hw>/<model>/<variant>/
  meta.yaml                              profiler/vLLM 버전, 유효 엔진 kwargs, GPU,
                                         타임스탬프, 압축 스윕 스펙, skew_fit 요약
  tp<N>/
    dense.csv                            layer, tokens, time_us
    per_sequence.csv                     layer, sequences, time_us
    attention.csv                        prefill_chunk, kv_prefill, n_decode, kv_decode, time_us
    moe.csv                              tokens, activated_experts, time_us   (MoE 전용)
    skew.csv                             원시 이기종 디코드 shot            (skew 활성화)
    skew_fit.csv                         피팅된 버킷별 alpha 테이블          (skew 활성화)
```

`<variant>`는 `--variant`가 설정되지 않으면 가중치 + KV dtype(예: `bf16`,
`bf16-kvfp8`, `fp8-kvfp8`)에서 자동 유도됩니다. 시간 단위는 **마이크로초**입니다.
yaml에서 `tp_stable: true`로 표시된 레이어(layernorm, sampler)는 TP=1에서 한 번
프로파일되고 writer에 의해 다른 `tp<N>/` 폴더로 복제됩니다.

프로파일러 Docker는 **vLLM v0.19.0**(`vllm/vllm-openai:v0.19.0` 또는 CUDA 13.x용
`v0.19.0-cu130`)을 사용합니다. MoE 훅은 강제 expert 라우팅을 위해
`FusedMoE.forward_native`를 패치합니다 — 메서드 이름은 버전에 따라 다릅니다.

### Skew 프로파일링 & alpha 피팅
FlashAttention의 varlen 커널은 디코드 배치의 kv 길이가 균일하지 않을 때 타일
패딩 + SM 불균형 비용을 지불합니다. 균일 어텐션 그리드는 이를 볼 수 없으므로(모든
shot이 단일 kv_decode 값을 사용), `skew.py`는 bimodal 배치에 대해 두 번째 스윕을
실행하고 케이스별로 세 가지 지연 시간을 측정합니다 — `t_mean`(모든 디코드가 배치
평균에서), `t_max`(모두 최대에서), `t_skew`(실제 bimodal 혼합). 정규화된 alpha ∈
[0, 1], `alpha = (t_skew − t_mean) / (t_max − t_mean)`는 skewed 배치가 mean→max
선을 따라 어디에 놓이는지를 시뮬레이터에게 알려줍니다.

- **스윕 구조**: Tier 1은 `_SKEW_REP = 4.0`에서 `(n, ratio, pc, kp, kvs)`에 대한
  factorial; Tier 2는 몇 개의 앵커 피벗(`skew ∈ {1.5, 2, 4, 8, 16}`)에서 skew 축
  스윕을 추가. CLI `SKEW_<axis>_FACTOR`(기본 2.0)는 해당 축을 기하학적으로 성기게
  함 — 높을수록 빠르고, 낮을수록 촘촘함. 계수와 그리드 스펙은
  `meta.yaml::skew_profile`에 기록.
- **피팅**: `fit_alpha.py`는 행을 5축 키 `pc | n_label | skew_rate_label |
  kv_big_label | kp_label`로 그룹화하고 셀별 가중 최소제곱 피팅을 실행. 확장된
  ~13k 샘플 데이터셋의 축 절제가 5축 방식을 선택(TP=1에서 테스트 p50/p90 ≈ 2.7% /
  14.8% vs 이전 3축 피팅의 3.5% / 16.4%).
- **데이터 기반 버킷 축**: `n`과 `kp`는 고유한 프로파일 값당 하나의 버킷(`kp=0`
  센티널 + overflow), `kv_big`은 관측된 최대까지 확장된 log-4x bin 사용,
  `skew_rate`는 고정 정규화 [0, 1] 방식, `pc`는 원본 키. 유도된 축은
  `meta.yaml::skew_fit.bucket_axes`에 기록; 시뮬레이터가 거기서 읽으므로 프로파일
  스윕을 확장하면 시뮬레이터 코드 변경 없이 더 미세한 해상도가 켜짐.
- **저장**: 전체 (bucket → alpha) 매핑은 `pc, n_label, skew_rate_label,
  kv_big_label, kp_label, alpha, n_samples` 열과 함께 `tp<N>/skew_fit.csv`로 spill.
  `meta.yaml::skew_fit.per_tp[tp]`는 요약(`method`, `n_samples`, `alpha_default`,
  `rel_err_p50/p90/p99`, `signed_mean`, `bucket_table` 포인터)만 유지. 이로써
  meta.yaml이 variant당 ~3100줄에서 ~100줄로 줄어듦. 시뮬레이터는
  `_load_perf_db()`에서 CSV를 메모리로 다시 로드.
- **비활성화**: `SKIP_SKEW=1`은 스윕을 완전히 건너뜀(시뮬레이터는 pooled 상수
  alpha로 폴백). `ONLY_SKEW=1`은 다른 모든 카테고리를 건너뛰고 `skew.csv` +
  `skew_fit.csv`만 갱신.

### 어텐션과 skew가 공유하는 실현 가능성 경계
균일 어텐션 스윕과 skew 스윕 모두 `n_reqs > max_num_seqs`(엄격한 `>`, `>=` 아님)로
상한을 두어 `n = MSQ` **pure** 케이스(prefill chunk 없음)가 들어맞도록 합니다.
이는 vLLM V1의 `input_batch` 버퍼를 정확히 `MSQ`까지 사용합니다. `n = MSQ`의 혼합
케이스는 `MSQ + 1` 요청이 필요하고 여전히 필터링됩니다. 런타임 워크로드가 `n =
X`에서 혼합 방식 데이터가 필요하면 `MAX_NUM_SEQS ≥ X + 1`로 프로파일하세요.

### 정식 레이어 이름 (시뮬레이터 ↔ 프로파일러, 통합)
시뮬레이터는 프로파일러의 카테고리별 CSV를 직접 소비합니다. 정식 레이어 이름은
vLLM 자체 속성 이름과 일치합니다. `trace_generator`는
`profiler/models/<model_type>.yaml`의 `sequence:` 섹션을 따라갑니다. 아래 표는 각
레이어가 프로파일러 CSV의 어디에 나타나며 시뮬레이터가 조회를 어떻게 키잉하는지
나열합니다.

| 레이어 | 카테고리 (CSV) | 키 의미 |
|-------|----------------|---------------|
| `embedding` | dense | `tokens = total_len` |
| `layernorm` | dense (tp_stable) | `tokens = total_len` |
| `qkv_proj` | dense | `tokens = total_len` |
| `qk_norm` | dense (tp_stable; Qwen3 전용) | `tokens = total_len` |
| `rotary_emb` | dense | `tokens = total_len` |
| `attention` | attention | `(prefill_chunk, kv_prefill, n_decode, kv_decode)` |
| `o_proj` | dense + 이후 ALLREDUCE (TP>1) | `tokens = total_len` |
| `gate_up_proj` | dense | `tokens = total_len` |
| `act_fn` | dense | `tokens = total_len` |
| `down_proj` | dense + 이후 ALLREDUCE (TP>1) | `tokens = total_len` |
| `final_layernorm` | dense (tp_stable) | `tokens = total_len` |
| `lm_head` | per_sequence | `sequences = num_requests` |
| `sampler` | per_sequence (tp_stable) | `sequences = num_requests` |
| `moe` | moe (항상 tp=1에서 프로파일; EP ALLTOALL로 감쌈) | `(local_tokens, activated_experts)` |

### 트레이스 생성기 구조
`trace_generator.py`는 아키텍처 yaml의 `sequence:` 섹션을 따라가며 각 반복을
생성합니다. 조합 가능한 헬퍼:
- `resolve_variant()` / `_load_perf_db()` / `_load_architecture()` — variant 폴더를
  결정하고, meta.yaml을 로드하고, 카테고리별 CSV를 로드하고, 아키텍처 카탈로그 +
  시퀀스를 연결.
- `_lookup_dense()` / `_lookup_per_sequence()` / `_lookup_attention()` /
  `_lookup_moe()` — 카테고리별 조회. Attention은 4D 조회 사용(`prefill_chunk,
  n_decode`에 대한 최근접이웃, `kv_prefill, kv_decode`에 대한 bilinear).
- `_emit_sequence()` — yaml의 정식 이름 리스트를 따라가며, `o_proj`/`down_proj`에
  TP ALLREDUCE를 부착하고, offloading이 활성화되면 NPU 어텐션 커널 앞에 PIM
  어텐션을 삽입하며, 시퀀스 레이어가 프로파일 CSV에 없으면 일회성 경고.
- `_emit_prologue()` / `_emit_pre_attn_layers()` / `_emit_post_attn_layers()` /
  `_emit_final_layers()` — `_emit_sequence`에 대한 얇은 래퍼.
- `_synthesize_interleaved_trace()` — 서브 배치 인터리빙을 위해 두 개의 `BatchCtx`
  객체를 번갈아 사용.
- `_emit_final_layers()` — final_layernorm → lm_head → sampler (sampler 출력은 REMOTE로)

### 트레이스 파일 형식
각 트레이스는 Chakra 변환기가 소비하는 탭 구분 텍스트 파일입니다:

```
COLOCATED		model_parallel_NPU_group: {npu_group}
{num_layers}
Layername    comp_time    input_loc    input_size    weight_loc    weight_size    output_loc    output_size    comm_type    comm_size    misc
embedding_0  5621         REMOTE:0     40            LOCAL         1050673152     LOCAL         81920          NONE         0            NONE
...
sampler_291  25933        LOCAL        2565120       LOCAL         0              REMOTE:0      40             NONE         0            NONE
```

- `comp_time`: 나노초 단위 지연 시간(profile.csv에서, 로드 시 변환)
- `input_loc`/`weight_loc`/`output_loc`: `LOCAL`(NPU), `REMOTE:{node_id}`(CPU), `CXL:{id}`
- `comm_type`: `NONE`, `ALLREDUCE`, `ALLTOALL`, 또는 차원 스코핑을 갖춘 `ALLREDUCE:1,0`, `ALLTOALL:0,1`
  (`:dim0,dim1` 접미사는 다차원 토폴로지를 위한 ASTRA-Sim의 `involved_dim` BoolList에 매핑)
- `misc`: `NONE` 또는 서브 배치 인터리빙을 위한 배치 태그(`BATCH_1`, `BATCH_2`)
- 첫 레이어(embedding) 입력은 `REMOTE`(CPU → NPU)에서, 마지막 레이어(sampler) 출력은 `REMOTE`(NPU → CPU)로
- MoE는 `EXPERT {i}` / `EXPERT END` 마커 사용(EXPERT 라인의 comm_type은 차원 스코핑 포함 가능)
- PIM은 `PIM {channel}` / `PIM END` 마커 사용

### 성능 DB와 지연 조회
시뮬레이터는 `_load_perf_db()`를 통해 카테고리별 CSV를 로드하고 카탈로그
카테고리별로 조회를 디스패치합니다: `_lookup_dense`(tokens에 대한 1D 선형),
`_lookup_per_sequence`(sequences에 대한 1D 선형), `_lookup_attention`(4D:
`(prefill_chunk, n_decode)`에 대한 최근접이웃 + `(kv_prefill, kv_decode)`에 대한
bilinear), `_lookup_moe`(`(tokens, activated_experts)`에 대한 2D, tp=1에서 프로파일).
모든 조회는 클램핑 대신 외삽합니다(time_us가 선형으로 확장). 지연 시간은 CSV에
마이크로초로 저장되고 로드 시 나노초로 변환됩니다. 캘리브레이션 스케일링 없음 —
프로파일된 지연 시간을 직접 사용.

Skew 보정을 갖춘 어텐션: `_lookup_attention_with_skew`는 두 번의 4D
조회(`kv_decode_mean`과 `kv_decode_max`에서)를 하고 `_skew_alpha`가
`meta.yaml::skew_fit`에서 결정한 `alpha`로 블렌딩합니다. 버킷 키는
`pc={pc}|{n_label}|{sr_label}|{kvb_label}|{kp_label}`이며, meta의
`skew_fit.bucket_axes`에 대해 구성됩니다(오래된 프로파일은 모듈 기본값으로 폴백).
`_hydrate_skew_fit_tables()`가 최초 로드 시 각 TP의 `skew_fit.csv`를 인메모리
`alpha_by_bucket` 맵으로 읽어들입니다.

프로파일 CSV 경로: `profiler/perf/<hardware>/<model>/<variant>/tp<N>/{dense,
per_sequence,attention,moe,skew,skew_fit}.csv`(`astra-sim/` 작업 디렉터리에서
`../profiler/perf/...`로 해석).

Variant 해석: `trace_generator.resolve_variant(dtype, kv_cache_dtype,
model_config)`은 프로파일러의 `effective_variant`를 반영 — 가중치 dtype은 CLI
값이나 모델 설정의 `torch_dtype`(기본 `bfloat16`)이며, KV dtype은 `auto`가 아닐 때
`-kv<short>` 접미사를 붙임. 런타임 조회는 결과 폴더가 존재하는지 검증하며,
불일치 시 누락된 variant를 가리키는 명확한 `FileNotFoundError`를 발생.

FP8 KV cache(`--kv-cache-dtype fp8`)는 `<dtype>-kvfp8` variant 폴더(예:
`bf16-kvfp8`)로 해석됩니다. `kv_cache_dtype` 파라미터는 `generate_trace` →
`resolve_variant` → `_load_perf_db`를 통해 전달됩니다. `memory_model.py`에서
`kv_fp`는 fp8에 대해 1바이트(다른 경우 `fp`)로, KV cache 메모리 사용량을 절반으로.

런타임 vs 프로파일 경고: `(hardware, model, variant)`의 최초 로드 시, 시뮬레이터는
CLI의 `--max-num-batched-tokens`와 `--max-num-seqs`를 `meta.yaml`의
`engine_effective` 값과 비교하고, 런타임이 프로파일러의 스윕 경계를 초과하면
일회성 경고를 로깅(조회가 외삽됨).

### Agentic 세션 지원 (의존성 체인)
시뮬레이터는 세션 내 LLM 호출이 도구 호출과 번갈아 의존성 체인을 형성하는 폐루프
agentic 워크로드(SWE-bench, tool-calling 에이전트)를 지원합니다.

**데이터셋 형식:** 각 JSONL 줄은 `sub_requests[]`를 가진 세션입니다. 각 하위 요청은
`input_toks`, `output_toks`, `tool_duration_ns`(이 LLM 호출 후 다음이 시작되기까지
대기 시간)를 가집니다. Flat 요청(`sub_requests` 키 없음)도 하위 호환성을 위해
지원됩니다. 두 형식은 같은 파일에 공존할 수 있습니다.

**라우터 의존성 추적** (`router.py`):
- `load_requests()`가 flat vs agentic 형식을 자동 감지. agentic 세션의 경우 첫
  하위 요청만 큐잉되고, 나머지는 `_deferred_sessions`에 저장
- `notify_request_completed(request_id, completion_time_ns)`가 다음 하위 요청을
  `completion_time + tool_duration_ns`에 방출하고 `_pending_requests`에 정렬되어 삽입
- `has_deferred_sessions()`가 세션이 진행 중일 때 조기 시뮬레이션 종료를 방지
- `scheduler.add_request()`가 동적으로 방출된 하위 요청이 큐에 들어올 때 도착 시각
  정렬 순서를 유지하기 위해 `bisect.insort`(`append` 아님)를 사용

**시간 전진:** 모든 인스턴스가 유휴이지만 지연된 하위 요청이 미래 도착 시각을
가질 때(도구 호출이 여전히 실행 중), `serving/__main__.py`는 busy-loop을 피하기
위해 `current`를 다음 대기 도착 시각으로 전진시킵니다.

### 스케줄러와 메모리 모델
- `scheduler.py`는 청크 프리필(기본 켜짐)을 갖춘 vLLM 스타일 continuous batching을 구현
- 토큰 예산은 `--max-num-batched-tokens`(기본 2048)와 `--max-num-seqs`(기본 128)로 제어
- `--long-prefill-token-threshold`가 청크 프리필의 스텝당 요청별 토큰을 상한
- KV cache는 `--block-size` 토큰 블록(기본 16)으로 관리
- RadixAttention을 통한 prefix caching이 기본 활성화(`--enable-prefix-caching`)
- `memory_model.py`의 메모리 추적은 NPU, CPU, CXL 계층을 다룸
- `calculate_sizes(parallel=)`가 레이어별 텐서 크기를 계산 — `parallel`은 dense
  레이어에는 TP, MoE expert에는 EP. `head_dim`, `q_dim`, `kv_dim` 사용
- MoE expert 가중치는 `tp_size`가 아닌 `ep_size`로 샤딩
- Prompt throughput(`add_done()`의 `prompt_t`)은 실제 계산된 프리필 토큰뿐 아니라
  prefix cache 히트 토큰을 포함. 이는 캐시된 것을 포함한 모든 입력 토큰을 세는
  vLLM의 보고된 prompt throughput과 일치

### CLI 인자 규약
CLI 플래그는 해당되는 경우 vLLM 이름을 따릅니다:
- `--dtype` (`float16`, `bfloat16`, `float32`, `int8`) — 모델 가중치 정밀도
- `--skip-prefill` — 프리필 단계 건너뜀(디코드 전용)
- `--request-routing-policy` (`LOAD`, `RR`, `RAND`, `CUSTOM`) — 인스턴스 간 요청 라우팅
- `--expert-routing-policy` (`BALANCED`, `RR`, `RAND`, `CUSTOM`) — MoE의 expert 토큰 라우팅
  (block-copy 최적화는 `--enable-block-copy`(기본 켜짐)로 별도 제어)
- Boolean 플래그는 `argparse.BooleanOptionalAction` 사용(예: `--enable-prefix-caching` /
  `--no-enable-prefix-caching`)

### Head 차원
일부 모델(예: Qwen3)은 `head_dim != hidden_size // num_attention_heads`입니다. 항상
다음을 사용하세요:
```python
head_dim = config.get('head_dim', n_embd // n_head)
q_dim = n_head * head_dim        # n_embd 아님
kv_dim = kv_head * head_dim      # n_embd // group 아님
```

### 모델 설정
모델 아키텍처 설정은 `configs/model/{org}/{model}.json`에 있습니다. 이들은
시뮬레이터가 필요로 하는 필드(`hidden_size`, `num_attention_heads`,
`num_hidden_layers`, `num_key_value_heads`, `intermediate_size`, `vocab_size`,
`head_dim`, `num_local_experts`, `num_experts_per_tok`)를 담은 HuggingFace
`config.json`의 부분집합입니다.

시뮬레이터는 `utils.py`의 `get_config(model_name)`을 통해 이들을 로드합니다.

### 클러스터 설정
`configs/cluster/`의 클러스터 설정은 하드웨어 토폴로지를 정의합니다. 주요 인스턴스
필드:
- `hardware`: `profiler/perf/<hardware>/`의 디렉터리 이름과 일치해야 함
- `model_name`: `configs/model/{model_name}.json`의 설정과 일치해야 함
- `num_npus`: 인스턴스의 총 GPU 수(선택, `tp_size * pp_size`에서 유추)
- `tp_size`: 텐서 병렬 차수(필수 또는 유추)
- `pp_size`: 파이프라인 병렬 차수(선택, 기본 1)
- `ep_size`: expert 병렬 차수(선택, MoE는 기본 `tp_size`, dense는 1)
- `dp_group`: DP 그룹 ID 문자열(선택, 같은 문자열을 가진 인스턴스는 expert 공유)
- `npu_mem.mem_bw`: NPU 메모리 대역폭(system.json에서 `local-mem-bw`로도 설정)
- `cpu_mem.mem_bw`: CPU 메모리 대역폭(memory_expansion.json에서 remote memory로 설정)
- `link_bw`: 노드 간 대역폭 GB/s(network.yml에서 설정)
- `link_latency`: 노드 간 링크 지연 시간 ns

병렬화 유추: 사용자는 부분 정보(예: `num_npus=4, tp_size=2`)를 제공할 수 있고
`config_builder.py`가 나머지(`pp_size=2`)를 유추합니다. 검증은 `num_npus = tp_size
* pp_size`와 `ep_size`가 `num_local_experts`를 나누어떨어지는지 보장합니다.

TP와 EP는 같은 GPU를 공유합니다: 비-MoE 레이어는 TP(ALLREDUCE), MoE 레이어는
EP(ALLTOALL) 사용. DP는 같은 `dp_group`을 가진 여러 인스턴스를 통해 달성.

`config_builder.py`는 클러스터 설정을 읽고 세 개의 ASTRA-Sim 입력 파일을
생성합니다:
- `astra-sim/inputs/network/network.yml` — 토폴로지와 대역폭
- `astra-sim/inputs/system/system.json` — 스케줄링 정책과 메모리 대역폭
- `astra-sim/inputs/memory/memory_expansion.json` — remote(CPU) 메모리 설정

### 작업 디렉터리
`serving/__main__.py`는 실행 초기에 cwd를 `astra-sim/`로 변경합니다. 시뮬레이터의
모든 상대 경로는 저장소 루트가 아니라 `astra-sim/`에서 해석됩니다. `configs/`,
`workloads/`, `profiler/`로 가는 경로는 저장소 루트 기준 상대 경로이며 코드에서
`../`로 접두됩니다.

### ASTRA-Sim을 위한 통신 크기
ASTRA-Sim은 collective에 대해 (NPU별이 아닌) **전체** 데이터 크기를 기대합니다.
내부적으로 N으로 나눕니다(`msg_size = data_size / nodes_in_ring`).
- `o_proj`와 `down_proj`의 ALLREDUCE: 전체 출력 텐서 크기 전달
- MoE의 ALLTOALL: 전체 activation 텐서 크기 전달

### 다차원 토폴로지와 `involved_dim`
DP+EP 구성의 경우 네트워크 토폴로지는 2D입니다: `npus_count: [tp_size,
dp_group_size]`. Collective는 COMM_COLL_NODE protobuf 노드의 `involved_dim`
BoolList 속성을 통해 특정 차원으로 스코핑됩니다:
- ALLREDUCE (TP): `involved_dim=[True, False]` — dim 0만
- ALLTOALL (EP): `involved_dim=[False, True]` — dim 1만 (또는 EP가 TP+DP에 걸치면 `[True, True]`)

`involved_dim`은 트레이스 `comm_type` 필드에 `ALLTOALL:0,1`로 인코딩됩니다(Chakra
변환기의 `_parse_comm_type`가 파싱). ASTRA-Sim의 `Workload::issue_comm()`가 이를
읽어 `generate_all_to_all()`에 전달하며, 이는 `involved_dim`이 false인 차원을
건너뜁니다.

`system.json` collective 구현은 토폴로지 차원당 하나의 항목을 가져야 합니다(예:
2D의 경우 `"all-to-all-implementation": ["ring", "ring"]`). `config_builder.py`가
DP 그룹의 존재 여부에 따라 이를 자동 생성합니다.

### MoE expert 블록
Expert 블록은 ASTRA-Sim을 위해 `EXPERT {i}` / `EXPERT END` 마커를 사용합니다. 각
EP 랭크는 로컬 토큰 수와 활성화된 expert를 기반으로 프로파일된 데이터에서 랭크별
지연을 얻습니다(`key_0=local_tokens, key_1=activated_experts`, tp=1에서 프로파일).
랭크는 병렬로 실행되고 ALLTOALL 배리어에서 동기화됩니다. Expert-to-rank 할당은
균등 파티셔닝을 사용합니다: `expert_id * ep_size // num_experts`.

### DP+EP wave 동기화
DP 그룹(같은 `dp_group`을 가진 인스턴스)의 경우, wave 동기화는 두 메커니즘으로
달성됩니다:
1. **Python 측 dp_pending 배리어**: 모든 DP 그룹 멤버가 배치를 스케줄할 때까지
   트레이스 생성이 지연됩니다. ALLTOALL `comm_size`는 그룹 전체의
   `max(total_len) * hidden_size * fp`로 동기화됩니다.
2. **ASTRA-Sim ALLTOALL 배리어**: 모든 DP 그룹 인스턴스의 `.et` 파일이 공유 워크로드
   폴더에 배치됩니다. 두 파일의 ALLTOALL collective가 일치하는 스트림 ID를 가져,
   ASTRA-Sim이 두 NPU가 collective에 도달할 때까지 블록하게 합니다.

한 DP 인스턴스가 유휴일 때(요청 없음), ALLTOALL 동기화에 참여할 수 있도록 dummy
배치(1 디코드 토큰)가 생성됩니다. 한 인스턴스가 모든 요청을 끝내면, 모든 DP 그룹
멤버가 끝날 때까지 계속 dummy 배치를 생성합니다.

### Chakra 그래프 변환기
Chakra 변환기(`astra-sim/extern/graph_frontend/chakra/src/converter/llm_converter.py`)는
텍스트 트레이스를 protobuf `.et` 파일로 변환합니다. 다음을 생성합니다:
- 첫 레이어의 입력을 위한 `MEM_LOAD_NODE`(REMOTE/CPU 메모리에서)
- 각 계산 레이어를 위한 `COMP_NODE`
- 마지막 레이어의 출력을 위한 `MEM_STORE_NODE`(REMOTE/CPU 메모리로)
- ALLREDUCE/ALLTOALL을 위한 `COMM_COLL_NODE`(선택적 `involved_dim` BoolList 속성)

변환기는 `ALLTOALL:0,1` 같은 `comm_type` 문자열을 `_parse_comm_type()`을 통해
파싱하여 `comm_type="ALLTOALL"`과 `involved_dim=[False, True]`로 분할합니다.

MEM_STORE 노드는 **마지막 레이어의** `output_memory_loc`을 사용합니다. 그래서
sampler(lm_head 아님)가 `output_loc=REMOTE:{node_id}`를 가져야 합니다.

메모리 위치 유형: `LOCAL`(NPU) = 1, `REMOTE`(CPU) = 2, `CXL` = 3, `STORAGE` = 4.
이들은 `astra-sim/astra-sim/system/AstraMemoryAPI.hh`의 C++ enum과 일치해야 합니다.

### Docker 환경
- **vLLM 컨테이너**(`python -m profiler`, `python -m bench`, `python -m
  workloads.generators`가 사용): `vllm/vllm-openai:v0.19.0`(또는 CUDA 13.x용
  `v0.19.0-cu130`)
  - `scripts/docker-vllm.sh`를 통해 실행
  - **LLMServingSim 저장소 루트**를 `/workspace`로 마운트; 컨테이너 cwd가
    `/workspace`이므로 `python -m profiler …` 등이 바로 동작
  - 최초 실행 시 `datasets`와 `matplotlib` 사전 설치(워크로드 생성기와 bench
    플롯이 사용하는 추가 의존성; 나머지는 vLLM이 제공)
  - 게이트된 설정 자동 다운로드를 위해 `scripts/docker-vllm.sh`에 `HF_TOKEN` 설정
- **시뮬레이터 컨테이너**: `astrasim/tutorial-micro2024` + Python 의존성
  - `scripts/docker-sim.sh`를 통해 실행
  - 저장소 루트를 `/app/LLMServingSim`에 마운트; ASTRA-Sim + Chakra는 최초 사용 시
    `scripts/compile.sh`를 통해 내부에서 빌드됨

## README와 docs 분리

저장소에는 의도적으로 범위를 구분한 두 개의 문서 표면이 있습니다:

- **`README.md`** — 최소한의 입구. About / Getting Started / Publications /
  Citation만. Logo + 링크 바(Website / Documentation / Contribute / Contact /
  Changelog)가 나머지 모든 것을 웹사이트로 안내. **README에 상세 콘텐츠(CLI 플래그
  표, 데이터셋 스키마, 프로파일러 설명, 검증 플롯 등)를 다시 추가하지 말 것** —
  이제 웹사이트에 있음.
- **`docs/`** — 공개 문서 사이트(Docusaurus 3, `https://llmservingsim.ai`에 배포).
  모든 장문 콘텐츠가 여기에 있음. 사이트별 규약은 `docs/AGENTS.md` 참고.

사용자에게 보이는 동작을 가진 새 기능을 추가할 때는 (README가 아니라) 웹사이트에
문서화하세요.

## 커밋 & Pull Request 가이드라인

- 짧은 명령형 커밋 메시지: `Fix incorrect evict_size accumulation`, `Add Qwen3
  model support`
- 커밋을 집중적으로 유지 — 커밋당 하나의 논리적 변경
- 검증에 사용한 정확한 명령을 포함하고 PR에 출력 CSV 경로를 명시
- 영향받는 시뮬레이션 모드와 사용한 설정/데이터셋을 기술

## 테스트 & 검증

전용 단위 테스트 스위트가 없습니다. 다음으로 검증하세요:
1. 가장 작은 관련 `python -m serving …` 시나리오를 실행하고 요청별 CSV를 검사.
2. 실제 vLLM에 대한 end-to-end 정확도 확인은 `python -m bench run`에 이어
   `python -m bench validate`를 사용(`bench/README.md` 참고).
3. 프로파일러 변경의 경우: `profiler/profile.sh`에서 `MODEL` / `HARDWARE`를 편집하고
   vLLM 컨테이너 내부에서 저장소 루트로부터 `./profiler/profile.sh`를 실행.

## 흔한 함정

- **`astra-sim/`를 편집하지 말 것** — 변경이 시뮬레이터 통합(예: `llm_converter.py`,
  `Workload.cc`, 입력 설정)을 대상으로 하지 않는 한
- **큰 파일을 커밋하지 말 것**: 생성된 트레이스, 출력 CSV, `.et` 파일은 gitignore됨
- **머신별 절대 경로를 사용하지 말 것** — 설정이나 코드에서 저장소 기준 상대 경로 사용
- **Request 속성에 `getattr` 폴백을 추가하지 말 것** — `Request.__init__`에서 모든
  속성을 초기화하고 직접 접근
- **`hidden_size == num_heads * head_dim`을 가정하지 말 것** — 설정의 명시적
  `head_dim` 사용
- **정식 vLLM 레이어 이름을 사용할 것**(`qkv_proj`, `o_proj`, `gate_up_proj`,
  `act_fn`, `down_proj`, `rotary_emb`, `qk_norm`, `attention`, `layernorm`,
  `final_layernorm`, `embedding`, `lm_head`, `sampler`, `moe`). 시뮬레이터가
  생성하는 모든 이름은 아키텍처 yaml의 카탈로그에도 나타나야 함.
- **프로파일러 CSV는 마이크로초를 저장**(`time_us` 열) — 시뮬레이터가 로드 시 1000을
  곱하고 나노초로 반올림
- **첫 및 마지막 트레이스 레이어는 REMOTE를 사용해야 함** — Chakra 변환기가 첫
  레이어의 input_loc에서 MEM_LOAD 노드를, 마지막 레이어의 output_loc에서 MEM_STORE
  노드를 생성; 둘 중 하나라도 local_mem 없이 LOCAL이면 ASTRA-Sim이 크래시
- **memory_expansion.json은 기본적으로 remote_mem만 가짐** —
  `--enable-local-offloading`을 사용하지 않는 한 local_mem은 설정되지 않음; LOCAL의
  가중치 로드는 메모리가 아닌 계산 시간을 거침
- **`config_builder.py`는 매 실행마다 ASTRA-Sim 입력을 재생성** —
  `astra-sim/inputs/` 파일이 유지되기를 기대하며 수동으로 편집하지 말 것
