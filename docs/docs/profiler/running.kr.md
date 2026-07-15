---
sidebar_position: 2
title: 실행
---

# 프로파일러 실행

프로파일러는 편집 가능한 템플릿인 `profiler/profile.sh`를 통해 호출됩니다. 상단의
변수를 프로파일하려는 것으로 변경한 뒤 실행합니다.

> 완전히 새로운 하드웨어 타깃(GPU 또는 비-GPU) 추가를 찾고 있나요? **[새 하드웨어
> 추가](./adding-hardware)**를 참고하세요. 이 페이지는 일상적인 "설정이 있고,
> 프로파일하고 싶다" 흐름을 다룹니다.

## 빠른 시작

`/workspace`의 vLLM Docker 컨테이너 내부에서:

```bash
# profiler/profile.sh 상단의 변수를 편집한 후:
./profiler/profile.sh
```

스크립트는 HF `config.json`의 `model_type` 필드에서 모델 아키텍처를 자동으로
해석하므로, 명령줄에서 지정하지 않습니다. 일치하는 아키텍처 YAML이
`profiler/models/<model_type>.yaml` 아래에 존재해야 합니다. 없으면 **[모델 아키텍처
추가](./adding-model-architecture)**를 참고하세요.

## `profile.sh`가 하는 일, 순서대로

1. `configs/model/<MODEL>.json`(원본 HF `config.json`)을 읽음. 없고 `MODEL`이 HF
   id이면 hub에서 다운로드하여 거기에 캐시.
2. `model_type`으로 일치하는 아키텍처 YAML을 선택.
3. 모델 설정을 tmpdir에 씀; 그에 대해 vLLM을 실행.
4. **dense / per_sequence / attention / moe** shot 그리드를 스윕하여
   `perf/<HW>/<MODEL>/<variant>/tp<N>/` 아래에 CSV를 씀.
5. (`SKIP_SKEW=0`, 기본값이면) 이기종 디코드 skew 스윕을 실행하고 버킷별 alpha를
   `skew_fit.csv`에 피팅.
6. 실행을 요약하는 `meta.yaml`을 씀.

`TP_DEGREES`의 각 TP 차수에 대해, 시뮬레이터는 `hf_overrides`를 통해 모델의 랭크별
형상을 나누어 그 TP를 단일 GPU에서 에뮬레이션합니다. **어떤 TP 차수를 프로파일하든
GPU 하나만** 필요합니다.

## 필수 변수

| 변수 | 의미 |
| --- | --- |
| `MODEL` | HF 스타일 `<org>/<name>`. `configs/model/<MODEL>.json`에 설정이 있어야 함(최초 실행 시 자동 다운로드) |
| `HARDWARE` | `perf/` 아래 폴더 이름이 되는 자유 형식 라벨. 의미 있는 것을 선택(예: `RTXPRO6000`, `H100`, `MI300X`) |

## 스윕 형태

| 변수 | 기본값 | 의미 |
| --- | --- | --- |
| `TP_DEGREES` | `1,2,4` | 콤마 구분 TP 차수. **`1`을 반드시 포함**(TP-stable 레이어는 TP=1에서 한 번 프로파일되고 다른 TP 폴더로 복제됨) |
| `MAX_NUM_BATCHED_TOKENS` | `2048` | 프로파일러가 shot-bypass 여유를 위해 내부적으로 `+MSQ`만큼 올림; meta 기록 시 다시 뺌 |
| `MAX_NUM_SEQS` | `256` | `n = runtime_MSQ`의 혼합 방식 케이스가 실현 가능하도록 `MSQ > runtime MSQ`로 프로파일 |

## 어텐션 그리드

4D 어텐션 스윕은 `(prefill_chunk, kv_prefill, n_decode, kv_decode)`를 커버합니다. 세
노브가 그 형태를 제어합니다:

| 변수 | 기본값 | 의미 |
| --- | --- | --- |
| `ATTENTION_MAX_KV` | `16384` | `kv_prefill`과 `kv_decode` 축의 상한 |
| `ATTENTION_CHUNK_FACTOR` | `2.0` | `prefill_chunk` 축의 기하 계수(2배씩) |
| `ATTENTION_KV_FACTOR` | `2.0` | `kv` 축의 기하 계수(2배씩) |

계수가 작을수록 축이 촘촘해짐(shot 많음, 느림); 클수록 성겨짐(shot 적음, 빠름).

## 측정 평균화

```bash
MEASUREMENT_ITERATIONS=3
```

shot당 타이밍 forward 횟수, 평균됨. 단일 샘플은 DVFS / 클럭 지터로 인해 큰 GEMM에서
15–25% 요동. `N=3`은 프로파일 시간 ~3배로 이를 ~5%로 줄임. 매우 촘촘한 수치가
필요하면 5로 올리세요.

## Skew 스윕

균일 어텐션 그리드 이후, 프로파일러는 시뮬레이터의 FlashAttention-varlen skew
보정을 구동하는 이기종 디코드 스윕을 실행합니다:

| 변수 | 기본값 | 의미 |
| --- | --- | --- |
| `SKIP_SKEW` | 미설정 | `1`로 설정하면 skew 스윕을 완전히 건너뜀. 시뮬레이터는 pooled 상수 alpha로 폴백 |
| `ONLY_SKEW` | 미설정 | `1`로 설정하면 **skew 단계만** 실행, dense / per_seq / attention / moe 미변경. `skew.csv` 갱신에 유용 |
| `SKEW_N_FACTOR` | `2.0` | `n`(총 디코드) 축 밀도. 높을수록 shot 적음 |
| `SKEW_PC_FACTOR` | `2.0` | `pc`(prefill chunk) 축 |
| `SKEW_KP_FACTOR` | `2.0` | `kp`(prefill history 길이) 축 |
| `SKEW_KVS_FACTOR` | `2.0` | `kvs`(small-decode kv) 축 |

skew 스윕은 케이스당 세 shot(`t_mean`, `t_max`, `t_skew`)을 발사하므로, `>2.0`
계수로 성기게 하면 프로파일 시간이 상당히 줄어듭니다. 방법론은 **[Skew & alpha
피팅](./skew-alpha-fit)**을 참고하세요.

## Resume vs force

| 변수 | 기본값 | 의미 |
| --- | --- | --- |
| `FORCE` | 미설정 | `1`로 설정하면 이 variant의 모든 CSV를 지우고 처음부터 재프로파일 |

기본값은 **resume**: 기존 CSV를 행 단위로 미리 로드하고, identity 키가 아직 없는
shot만 발사. 이를 통해 실현 가능성을 바꾼 후(예: `MAX_NUM_SEQS`를 128에서 256으로
상향) 이전 스윕을 몇 시간이 아닌 **몇 분** 만에 확장. Resume은 모든 카테고리와
skew에 적용; `FORCE=1`은 그것들을 모두 없앰.

## 출력 이름

| 변수 | 기본값 | 의미 |
| --- | --- | --- |
| `VARIANT` | 자동 유도 | variant 폴더 이름을 덮어씀 |

생략하면 `<variant>`는 `DTYPE` + `KV_CACHE_DTYPE`에서 자동 구성됩니다:

- `bfloat16` → `bf16`
- `bfloat16` + `fp8` KV → `bf16-kvfp8`
- `fp8` + `fp8` KV → `fp8-kvfp8`

이를 덮어쓸 일은 거의 없습니다. 이름 있는 실험 실행(양자화 방식, ablation)에서만
명시적으로 설정하세요.

## Dtype

| 변수 | 기본값 | 의미 |
| --- | --- | --- |
| `DTYPE` | `bfloat16` | 모델 가중치 dtype: `bfloat16` / `float16` / `float32` / `fp8`. 미설정 시 `torch_dtype`에서 유추 |
| `KV_CACHE_DTYPE` | `auto` | KV cache dtype: `auto`(`DTYPE` 상속) / `fp8` 등. `fp8`은 시뮬레이터에서 KV 메모리를 절반으로 |

## 자세한 출력(Verbosity)

```bash
VERBOSITY="--silent"        # 경고만
VERBOSITY="--verbose"       # DEBUG + vLLM stdout
VERBOSITY=""                # 기본값 (INFO)
```

## 다중 모델 배치 스윕: `profile-all.sh`

여러 모델에 걸쳐 새 GPU 타깃을 한 번에 준비하기 위해:

```bash
./profiler/profile-all.sh
```

이는 미리 정해진 모델 목록(현재 `Qwen/Qwen3-32B`,
`Qwen/Qwen3-30B-A3B-Instruct-2507`, `meta-llama/Llama-3.1-8B`)에 대해 TP=1과 TP=2로
`python -m profiler profile`을 루프로 감쌉니다. `profile.sh`의 모든 노브가 환경
변수로 인식됩니다:

```bash
HARDWARE=H100 \
TP_DEGREES=1,2,4 \
ATTENTION_CHUNK_FACTOR=1.5 \
./profiler/profile-all.sh
```

모델 목록을 변경하려면 스크립트 상단의 `MODELS=( ... )` 배열을 편집하세요. 이 파일은
안정적인 CLI로 취급하지 말고 그 자리에서 복사하거나 조정하도록 만들어졌습니다.

## 예상 실행 시간

RTXPRO6000급 하드웨어에서 단일 모델 + 단일 TP에 대한 대략적 수치
(`MAX_NUM_BATCHED_TOKENS=2048`, `MAX_NUM_SEQS=256`, 기본 계수):

| 단계 | 시간 |
| --- | --- |
| `dense` | 초 단위 |
| `per_sequence` | 초 단위 |
| `attention`(균일 4D 그리드) | 5–15분 |
| `moe`(MoE 전용) | 10–30분 |
| `skew` 스윕 | 10–25분 |
| `skew_fit`(후처리) | 초 단위 |

`profile-all.sh`를 사용한 전체 다중 TP, 다중 모델 스윕은 보통 **1–4시간** 실행됩니다.
varlen-skew 보정이 필요 없을 때 훨씬 빠른 패스를 위해 `SKIP_SKEW=1`을 사용하세요.

Rich 기반 로거가 단계별 진행 막대를 렌더링합니다; 더 조용한 실행을 위해 `--silent`로
stdout을 리다이렉트하세요.

## 출력

프로파일 데이터는 다음에 생성됩니다:

```
profiler/perf/<HARDWARE>/<MODEL>/<variant>/
├── meta.yaml
└── tp<N>/
    ├── dense.csv
    ├── per_sequence.csv
    ├── attention.csv
    ├── moe.csv         (MoE 모델 전용)
    ├── skew.csv         (skew 활성화 실행)
    └── skew_fit.csv     (skew 활성화 실행)
```

스키마 레퍼런스: **[출력 번들](./output-bundle)**.

## 팁

1. 새 `(hardware, model)` 조합을 준비할 때 **항상 `SKIP_SKEW=1`로 시작하세요** —
   균일 그리드를 먼저 끝낸 뒤, 나머지가 동작하는 것을 확인하면 skew를 추가.
2. **`profile.sh`는 제자리 편집을 의도합니다.** 플래그로 파라미터화하려 하지 마세요;
   크게 벗어나는 시나리오는 복사하세요.
3. **프로파일 재개는 세분화되어 있습니다**: 단일 shot이 크래시하면 문제를 고치고
   재실행 가능; 이전에 완료된 shot은 캐시된 채로 유지됨.
4. **어텐션 그리드를 먼저 성기게 하세요**. 4D 어텐션 스윕이 가장 긴 단계입니다.
   대략적 수치만 필요하면 `ATTENTION_CHUNK_FACTOR`를 `4.0`으로 올리고, 나중에
   정밀도를 위해 `2.0`으로 재실행하세요.
5. **CUDA 드라이버 버전에 걸쳐 프로파일하지 마세요.** 드라이버 업그레이드는 커널
   타이밍을 몇 퍼센트 변경합니다; 드라이버 변경 후 재프로파일하거나 drift를
   받아들이세요.

## 다음 단계

- **[출력 번들](./output-bundle)**: 방금 생성한 CSV의 스키마.
- **[Skew & alpha 피팅](./skew-alpha-fit)**: skew 스윕이 내부에서 하는 일.
