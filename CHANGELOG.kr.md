# Changelog

이 프로젝트의 모든 주목할 만한 변경 사항은 이 파일에 기록됩니다.
이 프로젝트는 [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) 규약을 따릅니다.

## [Unreleased]

### Added
- [llmservingsim.ai](https://llmservingsim.ai)의 공개 Docusaurus 3 문서 사이트.
  `docs/`에서 빌드되고 GitHub Actions Pages를 통해 배포됩니다. 기존
  `docs/index.html` 자리 표시자를 대체하고, 장문 콘텐츠(CLI 플래그 표, 데이터셋
  스키마, 프로파일러 설명, 검증 플롯 등)를 README에서 옮깁니다. 저장소의
  `README.md`는 이제 웹사이트로 연결되는 최소한의 입구(About / Getting Started /
  Publications / Citation)입니다. `README and docs split` 정책은 `AGENTS.md` /
  `CLAUDE.md`에 문서화되어 있습니다.
- `@easyops-cn/docusaurus-search-local`을 통한 문서 사이트의 로컬 검색. 빌드
  시점에 모든 `/docs/*`와 최상위 페이지 라우트(Contact, Changelog)를
  인덱싱합니다. 프로덕션 빌드가 실행되면 navbar 입력이나 Ctrl/Cmd-K로 접근
  (dev 모드는 인덱스를 생성하지 않음 — 로컬 테스트는 `pnpm build && pnpm serve`).
- `serving/core/memory_model.py`의 모듈 헬퍼
  `full_cluster_kv_bytes_per_token(model, fp, kv_cache_dtype)`. HuggingFace 스타일
  설정에서 직접 토큰당 전체 클러스터 KV 바이트를 계산하여, `MemoryModel.get_kv(1)
  * num_npus`의 랭크별 내림 나눗셈 반올림 오차를 피합니다. `__main__.py`가
  `MemoryModel`이 존재하기 전 시작 시점에 공유 prefix pool 크기를 잡는 데
  사용합니다.

### Changed
- `docs/docs/simulator/parallelism-mechanics.md`의 트레이스 수준 PP 모델링 설명
  전면 개편 — 스테이지 간 Chakra 레이어 분할 + `COMM_SEND` / `COMM_RECV`를
  스테이지 분할 그림과 함께 명시적으로 기술합니다. 시뮬레이터가 실제로 모델링하는
  바를 과소 기술하던 기존의 "스케줄링 전용 / 하한" 프레이밍을 대체합니다.
- `--expert-routing-policy` 기본값을 모든 곳에서 `BALANCED`로 문서화(expert-parallel
  예제, troubleshooting, trace-generation, `AGENTS.md`) — 이전 문서는 존재하지 않는
  `COPY` 기본값을 참조했습니다. `CUSTOM`을 request 및 expert 라우팅 옵션 양쪽에
  나열; 문서에서 `--enable-block-copy`를 라우팅 정책과 분리.
- `LOAD` request 라우팅 스코어링(`waiting * 4 + running`)을 다중 인스턴스 예제에
  문서화. 영향받는 페이지 전반에서 정책 목록을 불릿으로 재정렬.
- `MemoryModel.get_weight`이 이제 transformer 블록 가중치를 `pp_size`로 나눕니다
  (가장 무거운 랭크 보수적 경계: `embedding + n_layer//pp × per_block +
  final_layernorm + lm_head`). `MemoryModel.__init__`에 `pp_size` 파라미터 추가
  필요(`Scheduler`에서 전달). PP=1 동작은 불변 — 이 수정은 향후 PP > 1 실행에만
  영향(현재 어떤 클러스터 설정도 PP > 1을 사용하지 않음).
- `MemoryModel.apply_kv_cache_events`가 이제 CXL prefix storage와 CPU +
  prefix-sharing 모드에 대해 2차 계층 이벤트 큐를 비웁니다(기존에 처리하던 CPU
  non-sharing 케이스에 더해). CPU non-sharing 브랜치는 이벤트를 계속 `cpu_used`로
  연결; 다른 경로는 큐만 비웁니다(회계 영향 없음 — pool 메모리 사용량은
  `total_memory_usage`의 `total_size * kv_size`로 이미 추적됨). 시뮬레이션 수명
  동안 이벤트 큐가 무한히 커지는 것을 방지합니다.

### Fixed
- 청크 프리필이 prefix-cache 히트를 이중 집계했습니다. `schedule_with_prefix`에서
  `chunk_size = original_input - num_computed_tokens`는 이미 prefix-cache된 토큰을
  제외합니다(첫 `prefix_match`에서 `num_computed_tokens`가 `prefix_cache_hit`으로
  올라가기 때문). 그런데 스케줄러가 그 위에 `hit_len += prefix_hit`을 누적했고,
  `_build_batch_ctx`(trace_generator.py)가 prefix 히트를 두 번째로 빼서 — prefix
  caching이 켜진 모든 프리필 청크에서 `total_len`이 1로 붕괴되었습니다. Dense
  레이어 지연과 TP collective 사이징이 모두 `chunk_size` 대신 1 토큰으로
  조회되고 있었습니다. 수정: 두 번째 뺄셈 제거; 정리 과정에서 서브 배치
  인터리빙과 `Batch.hit_len` 필드 제거.
- `_make_sub_batch`(서브 배치 인터리빙)가 청크 프리필을 인식하지 못했습니다:
  `req.is_init`(이후 청크는 `is_init=False`이고 디코드로 오분류됨), `req.input`(이
  스텝의 청크가 아닌 전체 프롬프트 길이), `prefill_k_list=0`(이전 청크가 이미
  생성한 KV 무시)을 사용했습니다. 또한 두 서브 배치 간
  `prefill_q_list`/`prefill_k_list`/`decode_k_list`를 재설정하지 못해 batch1
  상태가 batch2로 새어 들어갔습니다. 이제 `batch.scheduled_tokens`(스케줄러가
  설정)를 읽고, `req.is_prefill()`을 기준으로 하며, 캐시에 이미 있는 KV에는
  `req.num_computed_tokens`를 사용합니다.
- `MemoryModel.evict_prefix_cache`가 2차 계층(CPU/CXL) 캐시를 `num_npus`배로
  과잉 축출했습니다. `space_needed`가 랭크별 `self._bytes_per_token`으로 계산된
  반면 각 2차 계층 토큰은 전체 클러스터 바이트(`per-rank × num_npus`)를 나타내기
  때문입니다. 이제 캐시 자체의 `kv_size`를 토큰당 바이트로 사용합니다(NPU는
  랭크별, 2차 계층은 전체 클러스터). TP=1은 영향 없음; TP>1은 스토리지 계층이 매
  spill마다 과잉 축출되어 prefix 히트율이 붕괴되고 있었습니다.
- `MemoryModel.evict_prefix_cache`의 조기 반환 가드가 `not enable_prefix_caching`
  AND `bytes <= 0` *둘 다*를 요구했습니다. `or`로 변경 — 둘 중 하나라도
  성립하면 조기 반환하려는 의도입니다.
- `scheduler.py`의 NPU→CPU offload alloc/free가 랭크별 바이트를 사용한 반면
  prefix-cache 이벤트는 전체 클러스터 바이트(`get_kv(tlen) * num_npus`)를
  추적했습니다. TP>1에서 두 경로 간 `cpu_used`가 어긋났습니다. Offload 경로가
  이제 기존 CPU 회계 규약에 맞게 `num_npus`로 스케일하므로, `cpu_used`가
  인스턴스당 일관되게 전체 클러스터 바이트가 됩니다.
- `MemoryModel.storage_cache_evicted_req`가 `new_last_node`가 **2차 계층** prefix
  트리에 속하는데도 `npu_prefix_cache.inc_lock_ref(new_last_node)`를 호출했습니다.
  외부 트리 노드에서 부모를 거슬러 올라가면 `npu_prefix_cache.root_node`에 결코
  도달하지 못하고 결국 `None`을 역참조하여, prefix caching이 켜진 상태로 NPU에서
  CPU/CXL 스토리지로 축출할 때 시뮬레이터가 크래시했습니다. 이제 올바른 트리를
  사용(PR #25).
- `MemoryModel.avail_size`가 `RadixCache.avail_size() * self._bytes_per_token`을
  반환했지만, `RadixCache.avail_size()`는 이미 바이트(`capacity -
  total_memory_usage()`)를 반환합니다. 추가 곱셈이 무의미하게 큰 값을 만들어,
  이를 기반으로 한 스케줄러 결정(예: `avail_size + evictable_size`)이 TP=1에서도
  과소 보수적이 되었습니다. 이제 바이트 값을 변경 없이 전달(PR #25).
- `serving/__main__.py`의 5곳(prefix-pool 생성 + CPU/CXL 사용량 표시)에
  하드코딩된 `131072` 토큰당 바이트(Llama-3.1-8B bf16 전용)를 모델 인식 값으로
  대체: pool은 이제 시작 시 `full_cluster_kv_bytes_per_token`으로 빌드되고, 표시
  라인은 각 `RadixCache` 자체의 `kv_size`를 사용합니다. Llama-3.1-8B가 아닌
  모델(Qwen3 계열 등)의 사용률 표시를 수정.
- CXL + prefix-sharing 표시 경로의 튜플 언패킹 크래시: `for i, cxl_id, cxl_pool
  in enumerate(prefix_pools):`가 `enumerate()`가 2-튜플을 산출하므로
  `ValueError: not enough values to unpack`을 발생시켰습니다. 올바른 2요소
  언패킹으로 대체.
- 청크 프리필 + prefix-cache 수정 후 검증 베이스라인 + 웹사이트 플롯 갱신. 평균 /
  P99가 이제 vLLM을 약간 과소 예측하는 대신 약간 과대 예측합니다(이전의 과소
  예측은 프리필 청크에 prefix-cache 히트가 있을 때마다 dense 레이어가 1 토큰으로
  조회되던 데서 기인). 세 개의 번들 설정 모두 여전히 TTFT / TPOT / latency 평균
  ~2.5% 이내에 들어옵니다.

### Security
- `fast-uri`를 ≥3.1.2로 업그레이드(CVE-2026-6321 퍼센트 인코딩된 점 세그먼트를
  통한 path traversal + CVE-2026-6322 퍼센트 인코딩된 authority 구분자를 통한
  host confusion, 둘 다 High 등급). 패키지가 transitive Docusaurus 의존성으로
  제공되므로 `pnpm.overrides`에 고정.
- `@babel/plugin-transform-modules-systemjs`를 ≥7.29.4로 업그레이드
  (GHSA-fv7c-fp4j-7gwp, CVE-2026-44728, High). 악의적 입력 컴파일 시 임의 코드
  생성; 7.12.0–7.29.3 영향. `@docusaurus/preset-classic`을 통해 7.29.0을
  제공했습니다. `pnpm.overrides`에 고정.
- `serialize-javascript`를 ≥7.0.5로 업그레이드(Dependabot, deferred function /
  regexp 직렬화를 통한 XSS). Docusaurus 3.10의 `copy-webpack-plugin`과
  `css-minimizer-webpack-plugin`이 transitive하게 가져옴.
- `uuid`를 ≥14.0.0으로 업그레이드(Dependabot, `buf`가 제공될 때 v3/v5/v6의 buffer
  경계 검사 누락). transitive 8.3.2(`sockjs`를 통해)와 11.1.1을 모두 대체.

## [v1.1.0] - 2026-04-26

### Added
- 기존 `llm_profile/` 모듈을 대체하는 새 vLLM 기반 레이어별 프로파일러
  (`profiler/`). worker extension 클래스를 통해 vLLM 내장 `layerwise_profile()`을
  사용하여 실제 vLLM 실행 경로에서 레이어별 CUDA 커널 타이밍을 캡처합니다.
  아키텍처는 HF 설정의 `model_type`으로 `profiler/models/` 아래 YAML 카탈로그에
  디스패치되며, 각 실행은 `perf/<hw>/<model>/<variant>/tp<N>/` 아래에
  카테고리별 CSV 번들(`dense.csv`, `per_sequence.csv`, `attention.csv`, MoE는
  `moe.csv`)을 마이크로초 단위 지연 시간으로 생성합니다. 기본 레이어별 프로파일
  방법론 — worker extension 클래스를 통해 실제 vLLM 엔진을 구동하고 `hf_overrides`
  샤딩으로 단일 GPU에서 TP=N을 에뮬레이션 — 은 [@waneon](https://github.com/waneon)에서
  차용했습니다.
- 기존 prefill/decode 분리 방식을 대체하는 통합 4D 어텐션 프로파일링
  (`attention.csv`). vLLM의 chunked-prefill 스케줄러가 실제로 매 스텝 생성하는 것과
  일치하는 `prefill_chunk × kv_prefill × n_decode × kv_decode`에 대한 단일
  테이블입니다. `ATTENTION_CHUNK_FACTOR` / `ATTENTION_KV_FACTOR`(기본 2.0 =
  2배씩)를 갖춘 기하 축이 프로파일 시간 대비 밀도를 조정합니다.
- 이기종 디코드 어텐션을 위한 skew 프로파일링 + 5축 alpha 피팅
  (`profiler/core/skew.py`, `fit_alpha.py`). 스윕은 bimodal 디코드 배치를 발사하고
  케이스별로 `(t_mean, t_max, t_skew)`를 측정; `fit_alpha`는 그 후 행을 5축 키
  `pc | n_label | skew_rate_label | kv_big_label | kp_label`로 그룹화하고 셀별
  가중 최소제곱을 실행합니다. 조회 시 시뮬레이터는 두 균일 어텐션 조회를
  피팅된 alpha로 블렌딩하여 균일 그리드가 볼 수 없는 FlashAttention
  타일 패딩 / SM 불균형 페널티를 복원합니다(`serving/core/trace_generator.py`의
  `_lookup_attention_with_skew` / `_skew_alpha`). 확장된 ~13k 샘플 데이터셋의 축
  절제가 이전 3축 피팅 대신 5축 방식을 선택(TP=1에서 테스트 p50/p90 ≈ 2.7% /
  14.8% vs 3.5% / 16.4%).
- skew 피팅을 위한 데이터 유도 버킷 축. `n`과 `kp` 버킷은 고유한 프로파일 값당
  하나씩(+ `kp=0` 센티널 + overflow); `kv_big`은 관측된 최대에 맞춘 log-4x bin
  사용; `skew_rate`는 고정 정규화 [0, 1] 방식; `pc`는 원본 키. 유도된 축은
  `meta.yaml::skew_fit.bucket_axes`에 기록되고 시뮬레이터가 거기서 읽으므로,
  `MAX_NUM_SEQS`나 `ATTENTION_MAX_KV`를 확장하면 시뮬레이터 코드 변경 없이 더
  미세한 해상도가 켜집니다.
- 축별 skew 밀도 노브: `SKEW_N_FACTOR` / `SKEW_PC_FACTOR` / `SKEW_KP_FACTOR` /
  `SKEW_KVS_FACTOR`(CLI: `--skew-*-factor`, 기본 2.0 = 2배씩). 높이면 해당 축을
  성기게 하고 프로파일 시간을 줄임; 유효 값은 `meta.yaml::skew_profile.factors`에
  기록.
- TP별 `skew_fit.csv` 파일이 전체 버킷별 alpha 테이블을 `meta.yaml`에서 빼내어
  후자가 읽기 좋게 유지됩니다(Qwen3-32B 2 TP에서 ~100줄 vs ~3100줄).
  `meta.yaml::skew_fit.per_tp[tp].bucket_table`이 `tp<N>/skew_fit.csv`를 가리킴;
  시뮬레이터가 `_load_perf_db()`에서 이를 `alpha_by_bucket`으로 다시 로드.
- `meta.yaml`의 압축 `attention_grid` / `skew_profile` 그리드 스펙(예: 전체 값
  목록 대신 `"0, 16-2048 x2"`).
- RTXPRO6000(NVIDIA RTX PRO 6000 Blackwell) 하드웨어 지원: 96 GB, 1597 GB/s,
  600W TDP.
- `involved_dim` 차원 스코핑을 통한 ASTRA-Sim ALLTOALL 동기화를 갖춘 DP+EP(Data
  Parallel + Expert Parallel) 지원. 같은 `dp_group`을 가진 인스턴스는 단일
  ASTRA-Sim 프로세스를 공유; 2D 토폴로지 `[tp_size, dp_group_size]`가 차원별
  collective 라우팅을 활성화(TP dim에서 ALLREDUCE, DP dim에서 ALLTOALL).
- DP 그룹을 위한 wave 동기화: Python 측 `dp_pending` 배리어가 트레이스 생성 전
  모든 인스턴스가 스케줄하도록 보장. ALLTOALL `comm_size`를 그룹 전체의
  `max(total_len)`으로 동기화. Dummy 배치가 유휴 인스턴스를 ALLTOALL 동기화에
  참여시킴.
- DP+EP MoE를 위한 `single_node_moe_dp_ep_instance.json` 클러스터 설정(2
  인스턴스, TP=1, EP=2, 동일 DP 그룹).
- 폐루프 워크로드(예: SWE-bench)를 위한 agentic 세션 지원. 새 JSONL 형식은
  `tool_duration_ns`를 갖춘 `sub_requests` 배열을 사용하여, 각 LLM 호출이 이전
  것의 완료와 도구 실행 시간을 기다리는 의존성 체인을 모델링합니다. 라우터는
  선행 요청이 끝나면 하위 요청을 동적으로 방출하여 다단계 agentic 워크플로우의
  정확한 시뮬레이션을 가능하게 합니다.
- `--num-reqs` CLI 인자(`--num-req` 대체), 기본값이 100에서 0으로 변경(데이터셋의
  모든 항목 로드). agentic 데이터셋의 경우 하위 요청이 아닌 세션을 셈.
- 예제 SWE-bench agentic 데이터셋
  (`workloads/swe-bench-qwen3-30b-a3b-50-sps0.2.jsonl`).
- `head_dim != hidden_size // num_attention_heads`인 모델을 위한 명시적 `head_dim`
  지원을 갖춘 Qwen3-32B 및 Qwen3-30B-A3B-Instruct-2507 모델 설정.
- FP8 KV cache 시뮬레이션 지원(`--kv-cache-dtype fp8`): 연산 지연 조회에
  `profile_fp8.csv`를 선택하고 메모리 모델에서 KV cache 메모리 사용량을 절반으로.
- FP8 KV cache 프로파일링 지원(receipts의 `kv_cache_dtype: "fp8"`, `profile_fp8.csv`
  출력).
- 청크 프리필 지원(기본 활성화, vLLM v1과 일치)과 스텝당 요청별 토큰 상한을 위한
  `--long-prefill-token-threshold`(청크 프리필 코어는
  [@HyunsuYEE](https://github.com/HyunsuYEE)).
- prefix caching(RadixAttention)과 호환되는 청크 프리필.
- 멀티 청크 프리필 중 잘못된 축출을 방지하기 위한 prefix cache lock 추적
  (`_prefix_locked`).
- 사전 컴파일된 vLLM 0.19.0 wheel과 함께 `uv`를 사용하는 비-Docker vLLM
  설치기(`scripts/install-vllm.sh`) ([@junwha](https://github.com/junwha)).
- End-to-end vLLM 벤치마크 + 시뮬레이터 검증 스위트(`bench/`,
  `python -m bench {run,validate}`로 호출). `bench run`은 워크로드를 실제 vLLM
  `AsyncLLM` 엔진으로 재실행하며 `output_toks`를 `SamplingParams(min_tokens=N,
  max_tokens=N, ignore_eos=True)`로 고정하여 결과가 동일 데이터셋에 대한
  시뮬레이터의 관점과 비트 단위로 비교 가능합니다. 커스텀
  `vllm.v1.metrics.loggers.StatLoggerBase`가 틱별 스케줄러 / 반복 통계를 씀;
  `vllm.v1.metrics.stats`의 `RequestStateStats`가 `requests.jsonl`에 저장됨.
  `bench validate`는 완료된 실행과 시뮬레이터의 `sim.csv` / `sim.log`를 로드하여
  throughput, running/waiting, TTFT/TPOT/latency-CDF 플롯과 수치 diff% 요약을 냄.
- 워크로드 생성기(`workloads/generators/`, `python -m workloads.generators
  sharegpt …`로 호출). 실행 컨텍스트 누적을 갖춘 멀티턴 ShareGPT 파서; 기본 소스
  `shibing624/sharegpt_gpt4`. 기본적으로 tokenizer 전용 모드(어시스턴트 턴에서
  출력 ID)로 실행하거나, `--use-vllm`으로 오프라인 배치 `vllm.LLM`을 구동하여
  최대 처리량으로 자유 생성 출력을 얻음. 선택적 `--fix-len`(랜덤 고정 길이 토큰)과
  `--pulse`(버스트 도착) 모드.
- `workloads/examples/` 아래 모델별 실행 템플릿(`gen-llama-3.1-8b.sh`,
  `gen-qwen3-30b-a3b.sh`, `gen-qwen3-32b.sh`).
- `bench/`, `scripts/`(vLLM 및 시뮬레이터 컨테이너 실행기, 베어메탈 vLLM 설치기,
  ASTRA-Sim 빌드를 위한 최상위 래퍼)를 위한 모듈 README.
- 시뮬레이터, 프로파일러, bench 간에 공유되는 Rich 기반 로거
  (`serving/core/logger.py`, `profiler/core/logger.py`, `bench/core/logger.py`).
  커스텀 ``_RichSimHandler``를 통해 원래의 `[HH:MM:SS.mmm] [Component]
  [node=X,inst=Y] LEVEL msg` 라인 형태를 유지(공개 API 불변 —
  ``configure_logger`` / ``get_logger`` / ``ComponentLoggerAdapter``가 기존 모든
  호출 지점에서 여전히 동작)하며 다음을 추가:
  - 어댑터의 ``.success()``(INFO에서 녹색 ✓)와 ``.summary()``(접두사 없이 그대로),
    그리고 프로파일러의 헬퍼를 반영하는 모듈 수준 ``print_banner()`` /
    ``print_input_config()`` / ``print_markup()`` / ``print_rule()``과
    ``stage(title)`` / ``progress(label, total)`` 컨텍스트 매니저.
  - Rich 테마 + ``soft_wrap=True``로 인터랙티브 터미널에서 색상이 렌더되고, 긴
    라인이 하나의 논리적 행에 유지되며, 리다이렉트된 파일(``> out.log``,
    ``nohup`` …)은 떠도는 ANSI 이스케이프 바이트 없이 깔끔한 평문 로그를 얻음.
    IDE 터미널이 TTY로 자기 식별하지 않을 때 ``FORCE_COLOR=1``이 여전히 색상을
    강제.
  - `serving/__main__.py`의 Banner / logo / input-config / simulation-results
    블록을 새 헬퍼로 마이그레이션(`bench/__main__.py`도 동일 banner / stage /
    progress 규약 사용); heartbeat 상태 트리(``├─`` / ``└─``)가 이제 각 라인을
    문자열로 빌드하고 일관된 색상을 위해 Rich markup으로 방출.
  - ``RadixCache.format_prefix_info()``, ``Scheduler.print_result()``,
    ``PowerModel.print_power_summary()``를 새 헬퍼를 중심으로 재작성.
    ``serving/utils.py``는 ANSI 색상 래퍼(``cyan`` / ``bold`` / ``ANSI_*`` / …)를
    잃고, logo / input-config 렌더러는 이제 ``logger.py``에 위치.
- `configs/model/`, `configs/pim/`, `workloads/`, `serving/`을 위한 README.
- AI 에이전트 캐시 파일을 위한 `.gitignore` 항목(`.claude/`, `.cursor/`,
  `.copilot/`, `.codex/`, `.aider*`, `.continue/`).

### Fixed
- skew 스윕 실현 가능성 필터가 엄격한 `n_reqs >= max_num_seqs`를 사용하여 모든
  `n = MSQ` 케이스(어텐션 스윕이 이미 허용하던 pure-decode 코너 포함)를
  버렸습니다. 어텐션과 일치하도록 `>`로 완화하고 pure `n = MSQ` shot을 해제.
  혼합 방식 `n = MSQ`(MSQ+1 요청 필요)는 여전히 필터링; 그 코너도 커버하려면
  런타임 MSQ보다 하나 큰 `MAX_NUM_SEQS`로 프로파일.
- 비-청크 프리필 경로의 `prefix_match` 호출 누락: 전체 프리필 요청에 대해 prefix
  cache 히트가 감지되지 않아, 청크 프리필이 비활성화되었을 때 prefix caching
  이점을 막았습니다 ([@junwha](https://github.com/junwha)).
- 레거시 Mixtral 프로파일러 모델의 타이머 참조 오타
  ([@junwha](https://github.com/junwha)).
- Prompt throughput이 이제 prefix cache 히트 토큰을 포함합니다. 이전에는 실제로
  계산된 프리필 토큰만 계수되어, prefix caching이 활성일 때 처리량이 vLLM이
  보고하는 prompt throughput보다 낮게 보였습니다.
- 전체 prefix cache 히트에 대해 prefix cache `is_init`이 결코 지워지지 않아, 매
  디코드 스텝마다 `total_requested_tokens`가 부풀고 `lock_ref` 누수가 발생.
- 전체 prefix 히트에 대해 `lock_prefix`가 호출되지 않아 시뮬레이션 종료 시 메모리
  누수 발생.
- MoE expert 지연이 두 EP 랭크를 하나의 GPU에 집계(2배 과대추정); 이제 각 GPU는
  자신 랭크의 토큰과 활성화된 expert만 사용.
- `memory_model.py`의 MoE 가중치 계산이 이제 expert 가중치 샤딩에 `tp_size`가 아닌
  `ep_size`를 사용.
- 상태 출력 타이밍: 일시적 "0 running" 상태를 피하기 위해 NPU 시작 시에만 출력.
- `system.json` collective 구현이 이제 토폴로지 차원과 일치(2D 토폴로지에 2
  항목) — 이전에는 1 항목이 ASTRA-Sim이 1 차원만 생성하게 함.
- DP 그룹 종료: 인스턴스가 done으로 표시하기 전에 모든 DP 멤버가 끝나기를 기다림.
- 잘못된 인자의 조용한 접두사 매칭을 방지하기 위한 `argparse`
  `allow_abbrev=False`.
- 레거시 프로파일러 layers/main.py의 누락된 `return parser.parse_args()` 추가
  ([@junwha](https://github.com/junwha), [@gleb-kun](https://github.com/gleb-kun)가
  보고 및 수정).

### Changed
- `--fp` 플래그를 `--dtype`로 대체(vLLM 스타일: `float16`, `bfloat16`, `float32`,
  `int8`).
- 명확성을 위해 `--gen` 플래그를 `--skip-prefill`로 대체.
- `--request-routing-policy` 기본값을 `RR`에서 `LOAD`(vLLM 스타일 가중 최소부하)로
  변경. 요청이 이제 사전 할당 대신 현재 시스템 상태를 기반으로 실시간 라우팅.
- 명확성을 위해 `--expert-routing-policy` `FAST`를 `COPY`로 개명(block copy 활성화).
- 클러스터 설정: `npu_num`/`npu_group`을 `tp_size`/`pp_size`/`ep_size`/`dp_group`로
  대체. 부분 설정 지원(예: `num_npus=4, tp_size=2`가 `pp_size=2` 유추). TP와 EP는
  같은 GPU 세트 공유; DP는 같은 `dp_group`을 가진 여러 인스턴스를 통해.
- MoE 모델링: EP 랭크별 지연 조회(`key_0=local_tokens, key_1=activated_experts`),
  균등 expert-to-rank 파티셔닝, 교차 DP 동기화를 위한 `involved_dim`을 갖춘
  ASTRA-Sim ALLTOALL.
- MoE `calculate_sizes`: `intermediate_size`(dense FFN dim)와 별개로
  `moe_intermediate_size`(expert별 FFN dim) 사용.
- `calculate_sizes` 파라미터 개명: `tp` → `parallel`(TP 또는 EP에 대한 일반화).
- 트레이스 `comm_type`이 이제 차원 스코핑 지원: `ALLREDUCE:1,0`, `ALLTOALL:0,1`.
- DP 그룹을 위한 네트워크 토폴로지: `system.json`의 차원별 collective 구현을 갖춘
  `npus_count: [tp_size, dp_group_size]`.
- analytical ALLTOALL 우회 함수 제거(`_inflate_comm_size`, `_ring_alltoall_time_ns`,
  `_bw_gb_to_bpns`) — 네이티브 ASTRA-Sim ALLTOALL로 대체.
- `link_bw`/`link_latency`를 `TraceCtx`와 `generate_trace`에서 제거(analytical
  폴백에 더 이상 불필요).
- 큰 배치 크기에서의 정확도 향상을 위해 지연 조회가 클램핑 대신 프로파일 범위를
  넘어 외삽.
- 프로파일러를 PyTorch Profiler + scikit-learn 예측기에서 직접 vLLM
  `layerwise_profile()` 방식으로 재작성. 아키텍처 yaml은 HF 설정의 `model_type`을
  키로 `profiler/models/`에 위치; CLI 플래그가 vLLM과 일치(`--dtype`,
  `--kv-cache-dtype`, `--max-num-batched-tokens`, `--max-num-seqs`, `--tp`,
  `--variant`). Docker를 vLLM v0.19.0(`vllm/vllm-openai:v0.19.0` 또는 CUDA 13.x용
  `v0.19.0-cu130`)에 고정.
- 기존 프로파일러를 참조용으로 `profiler/v0/` 아래에 보존.
- 프로파일러와 시뮬레이터 간 레이어 이름 통합: `qkv_projection`, `o_projection`,
  `ffn1`, `ffn2`, `attention`, `layernorm`(기존 이름 제거).
- Qwen3 같은 모델에서 올바른 텐서 크기 계산을 위해 명시적 `head_dim`과
  `q_dim`/`kv_dim`을 사용하도록 `memory_model.py` 업데이트.
- 조합 가능한 헬퍼(`TraceCtx`, `BatchCtx`, `_emit_layer`, `_emit_pre_attn_layers`,
  `_emit_post_attn_layers`)와 2D bilinear 보간을 갖춘 통합 프로파일 CSV 조회로
  `trace_generator.py` 재작성.
- Chakra 변환기의 MEM_STORE 노드 배치와 일치하도록 Sampler 출력 위치를
  `REMOTE`로 변경(기존 `lm_head`에 있었음).
- `--enable-attn-prediction` 플래그 제거(scikit-learn 예측기를 직접 프로파일된
  지연 조회로 대체).
- 클러스터 설정을 RTXPRO6000 하드웨어 스펙으로 업데이트.
- 전체 저장소 구조, 시뮬레이션 흐름, 트레이스 형식 문서화, 추가 함정으로
  `AGENTS.md` 확장.
- `--max-batch`를 `--max-num-seqs`로 개명(기본값: 128, vLLM과 일치); 이제 inflight
  배치 전체의 총 running 요청을 제한.
- `--enable-chunked-prefill`이 이제 기본 활성화(vLLM v1과 일치); 비활성화하려면
  `--no-enable-chunked-prefill` 사용.
- `--enable-prefix-caching`이 이제 기본 활성화(vLLM v1과 일치); 비활성화하려면
  `--no-enable-prefix-caching` 사용.
- 청크 및 비-청크 프리필 경로 모두에 vLLM 스타일 토큰 예산 기반 할당을 사용하도록
  스케줄러 재작성(`schedule_base`, `schedule_with_prefix`).
- KV cache 블록 할당이 vLLM 스타일 누적 올림 나눗셈 사용.
- Radix tree `cache_unfinished_req`가 이제 `req.input` 대신 `num_computed_tokens`를
  사용하여, 청크 간 올바른 증분 캐싱 가능.
- Prefix cache 메모리 회계를 free-before-allocate 순서로 변경.
- `memory_model.py`의 hash-to-length 맵을 중복 블록 해시를 처리하기 위해 `{hash:
  tlen}`에서 `{hash: [tlen, refcount]}`로 변경.
- 모든 `Request` 속성이 이제 `__init__`에서 제대로 초기화; 스케줄러와 radix tree
  전반의 `getattr` 폴백 제거.
- 디렉터리 재구성:
  - `cluster_config/` → `configs/cluster/`
  - `model_config/` → `configs/model/`
  - `pim_config/` → `configs/pim/`
  - `dataset/` → `workloads/`(시뮬레이터와 bench가 소비하는 ShareGPT 스타일 요청
    워크로드를 담는 디렉터리)
  - `output/` → `outputs/`
  - `script/` → `scripts/`
  - `llm_profile/` → `profiler/legacy_profiler/`(이후 `profiler/v0/`로 이동)
- 최상위 패키지 레이아웃을 Python 스타일 형제 모듈로 확정:
  - `inference_serving/` → `serving/`(내부는 `serving/core/` 아래; 이전에 패키지
    루트에 있던 모든 `.py`가 이제 한 디렉터리 더 깊이 위치); 진입점 `main.py`가
    `serving/__main__.py`가 되고 `python -m serving …`로 호출.
  - `llm_profiler/` → `profiler/`(중복된 `llm_profiler/profiler/` 패키지 계층
    붕괴), 내부는 `profiler/core/`와 `profiler/core/hooks/` 아래.
  - `bench/`를 동일 형태로 추가(`bench/core/`).
  - `workloads/`가 `workloads/generators/sharegpt.py` 아래에 ShareGPT 생성기 제공
    (`python -m workloads.generators sharegpt …`로 호출)하며 `workloads/examples/`
    아래에 모델별 실행 템플릿. 패키지는 HuggingFace `datasets` 라이브러리가
    깔끔하게 임포트되도록 의도적으로 `datasets/`라는 이름을 피함.
  - 모듈별 셸 스크립트는 모듈 홈에 위치(예: `profiler/profile.sh`, `bench/bench.sh`,
    `serving/run.sh`); 교차 관심사 환경 / 빌드 헬퍼만 `scripts/`에 유지
    (`docker-vllm.sh`, `docker-sim.sh`, `install-vllm.sh`, `compile.sh`).
- Evaluation 설정을 각 figure 폴더 내 `config/`에서 `configs/` 하위 디렉터리로 이동.
- 재구성된 예제와 사용 불가한 MoE 설정 주석 처리로 `run.sh` 업데이트.

### Removed
- `internal/` 디렉터리(디버그 문서와 스케줄러 테스트 이동 또는 제거).
- `scripts/` 배치 실험 스크립트(`run.sh` 예제로 대체).
- `evaluation/` 디렉터리(`ispass26-artifact` 브랜치에 보존).
- `--enable-attn-prediction` 플래그와 scikit-learn 어텐션 예측기.
- `--fp` 플래그(`--dtype`로 대체).
- `--gen` 플래그(`--skip-prefill`로 대체).
- `--expert-routing-policy FAST`(`COPY`로 개명).
- `serving/attn_utils.py`(오래된 scikit-learn 어텐션 feature 헬퍼).
- `npu_num`/`npu_group` 설정 필드(`tp_size`/`pp_size`/`ep_size`로 대체).
- `--num-req` 플래그(`--num-reqs`로 대체).
- analytical ALLTOALL 우회 함수(`_inflate_comm_size`, `_ring_alltoall_time_ns`).
- `evaluation/` 디렉터리(`ispass26-artifact` 브랜치에 보존).

---

## [v1.0.0] - 2026-02-25

### Added
- 설정 가능한 request 라우팅 정책(Round Robin, Random, Custom)을 갖춘 다중 인스턴스
  시뮬레이션.
- 인스턴스 간 Prefill/Decode(P/D) 분리 지원.
- expert 병렬화, expert offloading, 설정 가능한 라우팅 정책(Round Robin, Random,
  Fast, Custom)을 갖춘 Mixture of Experts(MoE) 지원.
- RadixAttention(SGLang 기반)을 사용한 prefix caching, CPU 및 CXL 메모리 전반의
  2차 계층 prefix cache 풀링 지원(`--enable-prefix-caching`,
  `--enable-prefix-sharing`).
- 반복 내에서 프리필과 디코드 단계를 오버랩하는 서브 배치 인터리빙
  (`--enable-sub-batch-interleaving`).
- 요청별 실시간 추정을 위한 scikit-learn 기반 어텐션 지연 예측기
  (`--enable-attn-prediction`).
- NPU, CPU, DRAM, 인터커넥트, NIC, 스토리지를 아우르는 노드별 전력 및 에너지
  모델링.
- 설정 가능한 대역폭과 지연 시간을 갖춘 CXL 메모리 확장 지원.
- 장치별 INI 설정(`configs/pim/`)을 갖춘 향상된 PIM(Processing-In-Memory) 모델.
- 모든 하드웨어, 토폴로지, 배치 파라미터를 단일 파일로 통합하는 클러스터 수준 설정
  시스템(`configs/cluster/*.json`).
- 클러스터 설정의 레이어별 가중치, KV cache, expert 배치 규칙.
- 추가 지연 지표: ITL(Inter-Token Latency)과 TTFT, TPOT, ITL의 p99.
- TPU-v6e-1용 하드웨어 성능 프로파일.
- 체계적 평가를 위한 배치 실험 스크립트(`scripts/`).
- Artifact 평가 스크립트와 참조 결과(`evaluation/`).
- MoE 모델과 전력 프로파일링 지원을 갖춘 로컬 모듈로 `llm_profile` 통합.

### Changed
- 모든 하드웨어와 토폴로지 파라미터가 이제 `cluster_config` JSON 파일로 지정; 호출별
  하드웨어 인자(`--model_name`, `--hardware`, `--npu_num` 등) 제거.
- 명령줄 인자 스타일이 언더스코어에서 하이픈으로 변경(예: `--cluster-config`,
  `--num-req`, `--block-size`).
- 데이터셋 형식이 `.tsv`에서 `.jsonl`로 변경.
- 빌드 프로세스를 `./compile.sh`와 `./docker.sh`로 통합.
- 성능 모델 디렉터리를 `perf_model/`에서 `llm_profile/perf_models/`로 재배치.
- 명확성을 위해 `serving/` 모듈 개명:
  - `control.py` → `controller.py`
  - `generate_graph.py` → `graph_generator.py`
  - `generate_trace.py` → `trace_generator.py`
  - `config_generator.py` → `config_builder.py`
  - `pim.py` → `pim_model.py`
- 잘못된 `evict_size` 누적 수정.

### Removed
- `trace_test/` 디렉터리(`evaluation/` 스크립트로 대체).
- 직접 호출별 하드웨어 인자(`--model_name`, `--hardware`, `--npu_num`,
  `--npu_group`, `--npu_mem`, `--remote_bw`, `--link_bw`).

---

## [v0.2.1] - 2025-07-18

### Added
- GPU 레이어 및 어텐션 지연 측정을 위한 PyTorch Profiler를 갖춘 `llm_profile` 모듈.
- Llama-3.1-8B-Instruct 모델 지원(GPT-3 6.7B를 기본 모델로 대체).
- 새 모델의 쉬운 추가를 위한 Hugging Face 모델 설정 지원.

### Changed
- 함수 이름을 snake_case로 표준화(예: `createNetworkConfig` →
  `create_network_config`, `calculateSizes` → `calculate_sizes`).
- 모델 설정 파일을 Llama-3.1-8B-Instruct 형식으로 업데이트.

### Fixed
- ASTRA-Sim 워크로드 그래프의 미해결 의존성으로 인한 collective 연산 stall.
- 완전 파이프라인 병렬화를 위한 네트워크 차원 계산(`npus_per_dim` 공식 수정).

---

## [v0.2.0] - 2025-06-04

### Changed
- ASTRA-Sim 서브모듈을 최신 버전으로 업데이트(브랜치 `v0.2.0`).
- Chakra를 최신 버전으로 업데이트.
- 네트워크 설정 형식을 JSON에서 YAML로 변경.
- `local_bw`와 `remote_bw` 파라미터를 `link_latency`로 대체.
- Conda 환경 의존성 업데이트 및 단순화.

---

## [v0.1.0] - 2025-01-03

### Added
- TensorRT-LLM 프로파일링 기반 GPU 성능 모델(NPU 시뮬레이터 대체).
- 네트워크 및 메모리 설정을 위한 자동 설정 생성기.
- 새 파라미터: `--hardware`, `--local_bw`, `--remote_bw`, `--link_bw`, `--fp`.
- 추가 지표: `queuing_delay`, TTFT, TPOT.
- 상세 실행 출력을 위한 verbose 로깅 옵션.

### Changed
- ASTRA-Sim 서브모듈 브랜치를 `artifact`에서 `v0.1.0`으로 업데이트.
- 출력 형식을 TSV에서 CSV로 변경.

### Removed
- Polymath 및 codelets_src 서브모듈(NPU 시뮬레이터 구성 요소를 성능 모델로 대체).

---

## [artifact] - 2024-06-23

### Added
- IISWC 2024 artifact로서의 초기 프로젝트 릴리스: "LLMServingSim: A HW/SW
  Co-Simulation Infrastructure for LLM Inference Serving at Scale".
- NPU 시뮬레이터 기반 co-simulation 인프라(ASTRA-Sim + Polymath + codelets_src).
- 평가 스크립트와 벤치마크 결과.
- Conda 환경 설정(`environment.yml`).
