# profiler

LLMServingSim을 위한 vLLM 기반 레이어별(layerwise) 프로파일러. 합성 배치로 실제
vLLM 엔진을 구동하고 레이어별 CUDA 커널 지연 시간을 기록합니다. 출력 CSV는
시뮬레이터의 트레이스 생성기에 입력됩니다.

## 디렉터리 레이아웃

```
profiler/                     Python 패키지 — `python -m profiler ...`
  __init__.py                 패키지 마커 + vLLM용 _typeshed shim
  __main__.py                 CLI 진입점 (profile / slice 서브커맨드)
  core/                       내부 구현
    runner.py                 오케스트레이션 루프
    config.py                 Architecture + ProfileArgs + 엔진 기본값
    engine.py                 vLLM 생명주기 (spin_up, probe_limits, spin_down)
    categories.py             Dense / PerSequence / Attention / Expert 카테고리
    skew.py                   이기종 디코드 skew 스윕 (skew.csv writer)
    fit_alpha.py              데이터 유도 버킷 축을 갖춘 5축 alpha 피팅
    writer.py                 CSV + meta.yaml writer (skew_fit.csv spill 포함)
    logger.py                 Rich 기반 로깅 & 진행 상황
    hooks/                    vLLM 내부 API 접점
      extension.py            worker extension 클래스
      batch.py                합성 SchedulerOutput 빌더
      timings.py              layerwise_profile 트리 파서
      moe_hook.py             FusedMoE 강제 라우팅 패치
  models/                     아키텍처 카탈로그 (HF model_type당 YAML 하나)
    llama.yaml
    qwen3.yaml
    qwen3_moe.yaml
    mixtral.yaml
    phimoe.yaml
  power/                      nvidia-smi / IPMI 전력 로깅 헬퍼
  perf/                       출력 루트 (hw/model/variant당 폴더 하나)
  profile.sh                  편집 가능한 사용자 실행 스크립트 — MODEL/HARDWARE/… 편집 후 실행
  profile-all.sh              헬퍼 템플릿: 여러 MODEL × TP 차수 스윕

scripts/                      공유 환경 / 빌드 진입점 (최상위)
  docker-vllm.sh              vLLM 컨테이너 실행 (저장소 루트 마운트)
  install-vllm.sh             로컬(비-Docker) uv venv 설정
```

## 빠른 시작

### 1. Docker 컨테이너 실행

```bash
./scripts/docker-vllm.sh
```

공식 vLLM 이미지(`vllm/vllm-openai:v0.19.0`, CUDA 13.x GPU의 경우
`:v0.19.0-cu130` — `scripts/docker-vllm.sh` 편집)에는 프로파일러에 필요한 모든
의존성(vllm, pydantic, pyyaml, rich, huggingface_hub)이 이미 포함되어 있습니다.
추가 pip 설치가 필요 없습니다.

컨테이너는 **LLMServingSim 저장소 루트**를 `/workspace`로 마운트하고 거기서
시작합니다. 게이트된 설정(Llama 등)이 최초 실행 시 자동으로 가져와지도록
`scripts/docker-vllm.sh`(`-e HF_TOKEN=…`)에 HuggingFace 토큰을 설정하세요.

### 2. 실행에 맞게 `profiler/profile.sh` 편집

이 스크립트는 템플릿입니다 — 열어서 `MODEL`과 `HARDWARE`를 변경하고, 선택적으로
나머지를 조정하세요. 아래 모든 노브는 `python -m profiler profile`의 CLI
플래그에 매핑됩니다. 설정하지 않은 셸 변수는 프로파일러의 내장 기본값으로
유지됩니다.

#### 필수

```bash
MODEL="meta-llama/Llama-3.1-8B"     # HF 스타일 <org>/<name>. 원본 HF config.json이
                                    # configs/model/<MODEL>.json에 있어야 함
                                    # (최초 실행 시 자동 다운로드).
HARDWARE="RTXPRO6000"               # 자유 형식 라벨 → perf/ 아래 폴더 이름.
```

#### 스윕 형태

```bash
TP_DEGREES="1,2,4"                  # 1을 포함해야 함; 한 GPU에서 한 번에 하나의 TP 프로파일
MAX_NUM_BATCHED_TOKENS=2048         # vLLM의 --max-num-batched-tokens (참고: 프로파일러는
                                    # shot-bypass 여유를 위해 내부적으로 +MSQ만큼 올리고
                                    # meta 기록 시 다시 뺌)
MAX_NUM_SEQS=256                    # vLLM의 --max-num-seqs. 런타임 MSQ보다 큰 MSQ로 프로파일
                                    # (예: 런타임 128을 목표로 하면 256으로 프로파일)하여
                                    # n = runtime_MSQ 혼합 코너가 실현 가능하도록.
```

#### 어텐션 그리드

```bash
ATTENTION_MAX_KV=16384              # kv_prefill / kv_decode 축의 상한
ATTENTION_CHUNK_FACTOR=2.0          # prefill_chunk 축의 기하 계수 (2배씩)
ATTENTION_KV_FACTOR=2.0             # kv 축의 기하 계수 (2배씩)
```

계수가 작을수록 해당 축이 촘촘해지고, 클수록 성겨집니다.

#### 측정 평균화

```bash
MEASUREMENT_ITERATIONS=3            # shot당 타이밍 forward 횟수, 평균됨. 단일 샘플은
                                    # DVFS / 클럭 지터로 인해 큰 GEMM에서 15–25% 요동;
                                    # N=3은 프로파일 시간 ~3배로 이를 ~5%로 줄임.
```

#### Skew 스윕

균일 어텐션 그리드 이후, 프로파일러는 시뮬레이터의 FlashAttention-varlen skew
보정(`skew.csv` + `skew_fit.csv`)을 구동하는 이기종 디코드 스윕을 실행합니다.
축별 기하 계수 4개와 모드 스위치 2개가 이를 제어합니다:

```bash
SKIP_SKEW=1                         # 스윕을 완전히 건너뜀 — 시뮬레이터는 pooled 상수
                                    # alpha로 폴백.
ONLY_SKEW=1                         # skew 단계만 실행 (dense / per_seq / attention /
                                    # moe 미변경). 균일 스윕이 이미 끝났고 skew.csv를
                                    # 갱신하거나 계수만 바꾸고 싶을 때 유용.

SKEW_N_FACTOR=2.0                   # n (총 디코드) 축 — 2.0 = 2배씩.
SKEW_PC_FACTOR=2.0                  # pc (prefill chunk) 축.
SKEW_KP_FACTOR=2.0                  # kp (prefill history 길이) 축.
SKEW_KVS_FACTOR=2.0                 # kvs (small-decode kv) 축.
```

계수를 2.0 초과로 올리면 해당 축이 성겨지고 프로파일 시간이 줄어듭니다(skew는
케이스당 3 shot을 발사하므로 성기게 하면 복합적으로 절약). 정확도가 중요한
축에서는 2.0 미만으로 낮춰 더 촘촘하게 샘플링하세요. 유효 값은
`meta.yaml::skew_profile.factors`에 기록됩니다.

#### 재개(Resume) vs 강제(Force)

```bash
FORCE=1                             # 이 variant의 모든 CSV를 지우고 처음부터 재프로파일.
```

기본값은 **재개**입니다: 기존 CSV를 행 단위로 미리 로드하고, identity 키가 아직
없는 shot만 발사합니다. 이를 통해 실현 가능성을 바꾼 후(예: 혼합 `n=128` 코너가
실현 가능하도록 `MAX_NUM_SEQS`를 128에서 256으로 상향) 이전 스윕을 몇 시간이
아닌 몇 분 만에 확장할 수 있습니다. 재개는 모든 카테고리와 skew에 적용됩니다.
`FORCE=1`은 그것들을 모두 없앱니다.

#### 출력 이름

```bash
VARIANT="my_experiment"             # 자동 유도된 <variant> 폴더 이름을 덮어씀.
```

생략하면 `<variant>`는 유효 DTYPE + KV dtype(`bf16`, `bf16-kvfp8`, `fp8-kvfp8`
등)으로 구성되므로 여러 정밀도를 프로파일할 때 충돌하지 않습니다. 이름 있는
실행(양자화 방식, 실험)에서만 명시적으로 설정하세요.

#### Dtype

```bash
DTYPE="bfloat16"                    # bfloat16 / float16 / float32 / fp8. 미설정 시
                                    # 모델의 torch_dtype에서 유추.
KV_CACHE_DTYPE="fp8"                # auto / fp8 / fp16 / bf16 — 기본값 "auto"
                                    # (DTYPE 상속). `fp8`은 variant 폴더에 `-kvfp8`
                                    # 접미사를 붙이고 시뮬레이터의 KV cache 메모리를
                                    # 절반으로 줄임.
```

#### 자세한 출력(Verbosity)

```bash
VERBOSITY="--silent"                # 경고만
VERBOSITY="--verbose"               # DEBUG + vLLM stdout
```

### 3. 실행

```bash
./profiler/profile.sh
```

프로파일러는:

1. `configs/model/<MODEL>.json`(원본 HF `config.json`)을 읽습니다. 파일이 없고
   `MODEL`이 HF 스타일 id이면, 설정을 hub에서 다운로드하여 해당 경로에 자동
   캐시합니다.
2. `model_type`으로 `models/` 아래 일치하는 아키텍처 yaml을 선택합니다(설정의
   필드가 yaml 파일 이름과 같아야 함). 일치하는 것이 없으면 명확한 오류와
   "available architectures" 목록으로 실패합니다.
3. 모델 설정을 임시 디렉터리에 쓰고 그에 대해 vLLM을 실행합니다 — 최초 fetch
   이후에는 HF 왕복이 필요 없습니다.
4. dense / per-sequence / attention(해당 시 MoE) shot 그리드를 스윕하여
   `perf/<HW>/<MODEL>/<variant>/tp<N>/` 아래에 CSV를 씁니다.

`<variant>`는 가중치 + KV dtype(`bf16`, `bf16-kvfp8`, `fp8-kvfp8`, …)에서
자동으로 이름 지어지므로, 서로 다른 정밀도가 충돌 없이 서로 다른 폴더에
저장됩니다. 이름 있는 실행(양자화 방식, 실험)에서만 `VARIANT=<name>`으로
덮어쓰세요.

### 4. 시뮬레이션에서 사용

시뮬레이터의 `trace_generator.py`는 클러스터 설정이 일치하는 하드웨어를
지정하고 CLI가 일치하는 모델을 선택하면
`profiler/perf/<hardware>/<model>/<variant>/tp<N>/*.csv`에서 자동으로 읽습니다.

### 여러 모델 스윕: `profiler/profile-all.sh`

몇 가지 미리 정해진 모델에 대한 루프로 `python -m profiler profile`을 감싸는
헬퍼 템플릿입니다. 현재 목록: `Qwen/Qwen3-32B`,
`Qwen/Qwen3-30B-A3B-Instruct-2507`, `meta-llama/Llama-3.1-8B` — 각각 동일
하드웨어에서 TP=1과 TP=2로 프로파일. 새 GPU 타깃을 한 번에 준비하는 데 유용합니다.

```bash
./profiler/profile-all.sh
```

모든 노브는 환경 변수입니다(argparse 없음). 기본값은 `profiler/profile.sh`와
일치하며, 다른 값이 필요하면 인라인으로 덮어쓰세요:

```bash
HARDWARE=H100 \
TP_DEGREES=1,2,4 \
ATTENTION_CHUNK_FACTOR=1.5 \
./profiler/profile-all.sh
```

인식되는 변수:
`HARDWARE`, `TP_DEGREES`, `MAX_NUM_BATCHED_TOKENS`, `MAX_NUM_SEQS`,
`ATTENTION_MAX_KV`, `ATTENTION_CHUNK_FACTOR`, `ATTENTION_KV_FACTOR`,
`SKEW_N_FACTOR`, `SKEW_PC_FACTOR`, `SKEW_KP_FACTOR`, `SKEW_KVS_FACTOR`,
`SKIP_SKEW`, `ONLY_SKEW`, `MEASUREMENT_ITERATIONS`, `DTYPE`,
`KV_CACHE_DTYPE`, `VARIANT`, `VERBOSITY`.

모델 목록을 변경하려면 스크립트 상단의 `MODELS=( ... )` 배열을 편집하세요.
이 파일은 안정적인 CLI로 취급하지 말고 그 자리에서 복사하거나 조정하도록
만들어졌습니다.

## 출력 스키마

각 `perf/<hw>/<model>/<variant>/` 디렉터리에는 하나의 `meta.yaml`(프로파일러 /
vLLM 버전, GPU, 타임스탬프, 유효 엔진 kwargs, 압축 스윕 스펙, skew fit 요약)과
프로파일된 TP 차수별로 하나의 `tp<N>/` 하위 폴더가 있습니다:

```
tp<N>/
  dense.csv              layer, tokens, time_us
  per_sequence.csv       layer, sequences, time_us
  attention.csv          prefill_chunk, kv_prefill, n_decode, kv_decode, time_us
  moe.csv                tokens, activated_experts, time_us          (MoE 전용)
  skew.csv               원시 이기종 디코드 shot (regime, n, nb, ratio,
                         skew, pc, kp, kvs, kv_big, kv_mean, t_mean_us,
                         t_max_us, t_skew_us, alpha)                  (skew 활성화 실행)
  skew_fit.csv           피팅된 버킷별 alpha 테이블 (pc, n_label,
                         skew_rate_label, kv_big_label, kp_label,
                         alpha, n_samples)                            (skew 활성화 실행)
```

시간 단위는 마이크로초입니다. Attention은 pure-prefill, pure-decode, mixed 커널
형상(vLLM의 chunked-prefill 스케줄러가 실제로 매 스텝 생성하는 것)을 아우르는
단일 4D 테이블입니다. 축은 기하급수적으로 증가합니다 — `prefill_chunk`와 kv
축은 각각 `ATTENTION_CHUNK_FACTOR`와 `ATTENTION_KV_FACTOR`(둘 다 기본값 2.0)로,
`n_decode`는 항상 2배씩.

`meta.yaml`에는 세 그룹의 스윕 메타데이터가 있습니다:

- `attention_grid` — 4D 어텐션 스윕의 상한(`max_kv`), 기하 계수(`chunk_factor`,
  `kv_factor`), `chunks` / `n_decode` / `kv` 축의 압축 스펙 문자열.
- `skew_profile` — skew 스윕의 축별 계수(`n`, `pc`, `kp`, `kvs`)와 압축 그리드
  스펙. `factors`가 `grid` 위에 나타나므로 값이 생성되기 전에 밀도 노브를 볼 수
  있음.
- `skew_fit` — TP별 피팅 요약(`method`, `n_samples`, `alpha_default`,
  `rel_err_p50/p90/p99`, `signed_mean`, `bucket_table` 포인터)과 공유
  `bucket_axes` 블록. 전체 버킷별 alpha 매핑은 각 TP의 `skew_fit.csv`에 있음.

## Skew 프로파일링 & alpha 피팅

FlashAttention의 varlen 커널은 디코드 배치의 kv 길이가 균일하지 않을 때
타일 패딩 + SM 불균형 페널티를 지불합니다. 균일 어텐션 그리드는 이를 볼 수
없으므로(거기서는 모든 shot이 모든 디코드를 같은 kv에 둠), 의도적으로 만든
bimodal 배치에 대해 두 번째의 더 좁은 스윕을 실행합니다:

```
t_mean   — 모든 디코드를 배치의 평균 kv로 균일하게
t_max    — 모든 디코드를 배치의 최대 kv로 균일하게
t_skew   — 실제 skewed 배치 [nb × kv_big, (n-nb) × kvs]
```

이 셋으로부터 케이스별 정규화된 alpha를 얻습니다:

```
alpha = (t_skew - t_mean) / (t_max - t_mean) ∈ [0, 1]
```

시뮬레이터는 이를 조회 시 적용합니다:

```
t_predicted = t_mean_lookup(batch.mean_kv) +
              alpha(batch.shape) × (t_max_lookup(batch.max_kv) − t_mean_lookup(batch.mean_kv))
```

### 스윕 구조

`skew.csv`는 두 계층으로 구성됩니다:

- **Tier 1** — 단일 대표 skew 계수(`_SKEW_REP = 4.0`)에서 `(n, ratio, pc, kp,
  kvs)`에 대한 factorial. 대부분의 행을 제공하고, 피팅이 구별하는 모든 (pc,
  n_bin, kv_big_bin, kp_bin, skew_rate_bin) 셀을 커버.
- **Tier 2** — 몇 개의 앵커 피벗에서 `skew ∈ {1.5, 2.0, 4.0, 8.0, 16.0}`인
  skew 축 스윕. `skew ≠ 4.0`인 행의 유일한 원천이며, outlier 디코드가 늘어날
  때 alpha가 어떻게 포화되는지 커버.

(kvs 축을 위한 이전 Tier 3은 T1이 kvs를 따라 충분히 촘촘해지면서 제거됨.)

### 밀도 노브

다섯 축 모두 축별 기하 계수(기본값 2.0 = 2배씩)로 사용자가 제어 가능합니다:

| 변수 | 축 | 효과 |
|---|---|---|
| `SKEW_N_FACTOR` | `n` (총 디코드) | 성기게 하여 더 적은 배치 크기 발사 |
| `SKEW_PC_FACTOR` | `pc` (prefill chunk) | 성기게 하여 prefill-chunk 스케일 건너뜀 |
| `SKEW_KP_FACTOR` | `kp` (prefill history) | 긴 컨텍스트 앵커를 성기게 |
| `SKEW_KVS_FACTOR` | `kvs` (small-decode kv) | kv 스윕을 성기게 |

값이 높을수록 → 포인트가 적음 → 스윕이 빠름. 낮을수록 → 그리드가 촘촘함 →
미세 구조 근처에서 alpha가 더 정확함. 유효 값은 `meta.yaml::skew_profile.factors`에
기록되므로 나중에 어떤 밀도가 어떤 CSV를 생성했는지 알 수 있습니다.

### 5축 alpha 피팅

`fit_alpha.py`는 프로파일링 직후 실행되며 행을 5-튜플 버킷 키로 그룹화합니다:

```
pc | n_label | skew_rate_label | kv_big_label | kp_label
```

각 셀은 가중 최소제곱(weighted-LS) alpha를 얻습니다. 확장된 ~13k 샘플
데이터셋에 대한 축 절제(ablation)로 이 5축 방식이 선택되었습니다(TP=1에서
테스트 p50 / p90 / p99 ≈ 2.7 / 14.8 / 44.1 % vs 이전 3축 피팅의 3.5 / 16.4 / 39.9).

**버킷 축은 데이터 기반입니다.** `n`과 `kp` bin은 고유한 프로파일 값당 하나씩
유도되며(`kp=0`용 센티널 bin과 스윕 범위를 넘는 런타임 값을 위한 overflow bin
포함), `kv_big`은 관측된 최대에 맞춘 log-4x 2배 방식을 사용하고, `skew_rate`는
고정 bin 경계를 가진 정규화된 [0, 1] 지표이며, `pc`는 원본으로 사용됩니다(버킷화
안 함). 따라서 모든 프로파일 그리드 포인트가 자체 alpha 열이 됩니다. 이는
스윕을 확장하면(`MAX_NUM_SEQS`를 128 초과로, `ATTENTION_MAX_KV`를 16k 초과로
상향) 코드 변경 없이 영향받는 축에서 적절한 해상도가 켜진다는 의미입니다 —
피터(fitter)가 사용한 축을 `meta.yaml::skew_fit.bucket_axes`에 쓰고 시뮬레이터가
거기서 읽습니다.

### 비활성화 / 재피팅

- `SKIP_SKEW=1`로 스윕을 완전히 건너뜁니다(균일 어텐션 그리드만; 시뮬레이터는
  모듈 수준 폴백 alpha 사용).
- `ONLY_SKEW=1`로 다른 모든 카테고리를 건너뛰고 `skew.csv` + `skew_fit.csv`만
  갱신합니다 — 그리드를 확장하거나 계수를 조정한 후 유용.

## 아키텍처 yaml

`models/<model_type>.yaml`은 하나의 vLLM 모델 계열의 클래스 구조(embedding,
layernorm, qkv_proj, attention 등)를 기술합니다. 파일 이름은 HuggingFace
`model_type` 값(`llama`, `qwen3`, `qwen3_moe`, `mixtral`, `phimoe`)과
같습니다. 카탈로그 항목은 정식 이름을 vLLM 클래스에 바인딩하며, 중복 클래스
이름을 구별하기 위한 선택적 `within:` 부모를 가집니다:

```yaml
catalog:
  dense:
    qkv_proj:
      vllm: QKVParallelLinear
    layernorm:
      vllm: RMSNorm
      within: LlamaDecoderLayer    # final_layernorm과 구별
      tp_stable: true
    …
  per_sequence:
    lm_head:
      vllm: LogitsProcessor
    sampler:
      vllm: Sampler
      tp_stable: true
  attention:
    attention:
      vllm: Attention
  moe:                             # MoE 계열에만 존재
    moe:
      vllm: Qwen3MoeSparseMoeBlock
```

`tp_stable: true`는 커널 비용이 TP에 따라 변하지 않는 레이어(layernorm,
sampler)를 표시합니다. 이들은 TP=1에서 한 번 프로파일되고 writer에 의해 다른
tp 폴더로 복제됩니다.

## 새 모델 추가

1. **HF `config.json`을 넣기** — `configs/model/<org>/<name>.json`. (또는
   컨테이너에 `HF_TOKEN`이 설정되어 있으면 프로파일러가 최초 실행 시 자동
   다운로드.)
2. **모델의 `model_type`이 이미 지원되면**(llama / qwen3 / qwen3_moe / mixtral
   / phimoe) 끝입니다 — `profiler/profile.sh`에서 `MODEL=`을 편집하고 실행.
3. **새 아키텍처 계열이면**(예: `gemma2`, `deepseek_v3`):
   * 새 계열의 vLLM 클래스를 정식 이름에 매핑하는 `models/<model_type>.yaml`을
     생성.
   * `../vllm/vllm/model_executor/models/<name>.py` 아래의 모델 소스를
     교차 참조하여 decoder / attention / MLP 클래스 이름을 식별.
   * 프로파일러를 실행 — 새 yaml이 자동으로 선택됨.

## 커스텀 모델 형상

가상 형상(예: "Llama-300B": 16384 hidden × 128 heads × 80 layers)을 프로파일하려면,
원하는 차원과 인식되는 `model_type`을 가진 커스텀 설정을
`configs/model/custom/my-model.json`에 넣기만 하면 됩니다:

```json
{
  "architectures": ["LlamaForCausalLM"],
  "model_type": "llama",
  "hidden_size": 16384,
  "intermediate_size": 53248,
  "num_attention_heads": 128,
  "num_hidden_layers": 80,
  "num_key_value_heads": 16,
  "vocab_size": 128256,
  "max_position_embeddings": 32768,
  "rms_norm_eps": 1e-05,
  "rope_theta": 500000.0,
  "tie_word_embeddings": false,
  "hidden_act": "silu"
}
```

`profile.sh`에서 `MODEL="custom/my-model"`을 설정하고 실행하세요. 프로파일러가
이 정확한 설정을 vLLM용 임시 디렉터리에 쓰므로, 측정하려는 형상에 대해 HF
저장소가 존재할 필요가 없습니다.

## 자세한 출력(Verbosity)

```
(기본값)                     INFO — TP 제한, 스테이지 타이밍, 진행 상황.
--silent                     WARNING — 경고만.
--verbose                    DEBUG + vLLM stdout/stderr.
--log-level {DEBUG,INFO,…}   명시적 덮어쓰기.
```

`profiler/profile.sh`에서 `VERBOSITY="--silent"` / `"--verbose"`로 설정하거나,
`python -m profiler profile`에 `--log-level X`를 직접 전달하세요.

## Slice 갱신 (부분 재프로파일)

첫 전체 스윕 이후, 모든 것을 다시 하지 않고 한 카테고리(예: 어텐션 그리드 튜닝)를
반복할 수 있습니다:

```bash
python -m profiler slice meta-llama/Llama-3.1-8B \
    --hardware RTXPRO6000 --tp-refresh 1 --group attention
```

해당 `tp1/attention.csv`만 덮어쓰고 `meta.yaml`을 갱신합니다.
