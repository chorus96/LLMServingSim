---
sidebar_position: 6
title: 모델 아키텍처 추가
---

# 모델 아키텍처 추가

프로파일러는 HF 설정의 `model_type` 필드로 디스패치합니다. 모델의 `model_type`이
이미 `profiler/models/` 아래의 YAML에 매핑되면 끝입니다 — `profile.sh`만 실행하세요.
아니면 YAML을 추가해야 합니다.

이 페이지는 그 경우에 관한 것입니다.

## 새 YAML이 필요한 때

`cat configs/model/<your-org>/<your-model>.json | jq .model_type`을 실행하고 번들된
아키텍처와 비교하세요:

| `model_type` | YAML | 커버 |
| --- | --- | --- |
| `llama` | `llama.yaml` | Llama 3.x dense (8B / 70B / 405B / 커스텀 형상), Mistral 7B, 같은 블록 구조의 파생물 |
| `qwen3` | `qwen3.yaml` | Qwen3 dense (0.6B / 4B / 7B / 14B / 32B), head별 `qk_norm` 포함 |
| `qwen3_moe` | `qwen3_moe.yaml` | Qwen3 MoE (30B-A3B, 235B-A22B) |
| `mixtral` | `mixtral.yaml` | `MixtralForCausalLM` (8x7B, 8x22B) |
| `phimoe` | `phimoe.yaml` | `PhiMoEForCausalLM` (Phi-3.5-MoE) |

`model_type`이 이 중 하나이면 아무것도 할 필요가 없습니다 — 기존 YAML이 처리합니다.

*새* `model_type`(예: `gemma2`, `deepseek_v3`, `gpt_oss`)이면 새 YAML이 필요합니다.
계속 읽으세요.

## 시뮬레이터 코드 변경도 필요한 때

새 모델의 반복별 흐름이 표준 패턴에 맞으면 YAML만 추가하는 것으로 충분합니다:

```
prologue → pre_attn → post_attn → (mlp_dense | mlp_moe) → head
```

새 모델이 진정으로 새로운 블록 구조를 가지면 — sliding window attention,
multi-latent attention(MLA, DeepSeek V3 같은), dual MLP 디코더 —
`serving/core/trace_generator.py`도 확장하여 새 시퀀스를 따라가고 올바른 collective를
부착해야 합니다. 이 페이지 끝에서 다룹니다.

## YAML 구조

각 아키텍처 YAML은 두 개의 최상위 섹션을 가집니다:

- `catalog:`: 정식 레이어 이름을 vLLM 내부 클래스 이름에 매핑. 프로파일러가 이를
  사용해 타이밍할 올바른 모듈 객체를 찾음.
- `sequence:`: 반복별로 레이어가 실행되는 순서를 선언. 프로파일러가 시퀀스 레이어당
  하나의 shot을 생성; 시뮬레이터의 `trace_generator`가 트레이스 시 같은 리스트를
  따라감.

### 최소 예제: `llama.yaml`

```yaml
catalog:
  embedding:
    cls: VocabParallelEmbedding
    category: dense
  layernorm:
    cls: RMSNorm
    category: dense
    tp_stable: true
  qkv_proj:
    cls: QKVParallelLinear
    category: dense
  rotary_emb:
    cls: RotaryEmbedding
    category: dense
  attention:
    cls: Attention
    category: attention
  o_proj:
    cls: RowParallelLinear
    category: dense
    tp_collective: ALLREDUCE
  gate_up_proj:
    cls: MergedColumnParallelLinear
    category: dense
  act_fn:
    cls: SiluAndMul
    category: dense
  down_proj:
    cls: RowParallelLinear
    category: dense
    tp_collective: ALLREDUCE
  final_layernorm:
    cls: RMSNorm
    category: dense
    tp_stable: true
  lm_head:
    cls: ParallelLMHead
    category: per_sequence
  sampler:
    cls: Sampler
    category: per_sequence
    tp_stable: true

sequence:
  prologue:
    - embedding
    - layernorm                   # 블록 0 전의 input rms_norm
  pre_attn:
    - layernorm
    - qkv_proj
    - rotary_emb
  post_attn:
    - o_proj
    - layernorm                   # post_attention_layernorm
  mlp_dense:
    - gate_up_proj
    - act_fn
    - down_proj
  head:
    - final_layernorm
    - lm_head
    - sampler
```

### `catalog` 필드 레퍼런스

| 필드 | 필수 | 의미 |
| --- | --- | --- |
| `cls` | ✓ | vLLM 클래스 이름(속성 조회를 통해 모듈 객체를 해석하는 데 사용) |
| `category` | ✓ | `dense` / `per_sequence` / `attention` / `moe` 중 하나 |
| `tp_stable` | 선택 | 레이어의 지연이 TP 차수에 의존하지 않으면 `true`(예: layernorm, sampler). writer가 TP=1에서 한 번 프로파일하고 다른 `tp<N>/` 폴더로 복제 |
| `tp_collective` | 선택 | TP > 1이면 이 레이어 이후 발사되는 collective: `o_proj`와 `down_proj`는 `ALLREDUCE`. 다른 레이어는 필요 없음 |

### `sequence` 섹션 레퍼런스

| 그룹 | 실행 | 비고 |
| --- | --- | --- |
| `prologue` | 각 반복 시작에 한 번 | 임베딩 조회 + 초기 input layernorm |
| `pre_attn` | 디코더 블록당 한 번 | qkv_proj + rotary_emb + (Qwen3면 qk_norm) |
| `post_attn` | 디코더 블록당 한 번 | o_proj + post_attention_layernorm |
| `mlp_dense` | 디코더 블록당 한 번(dense 모델) | gate_up_proj + act_fn + down_proj |
| `mlp_moe` | 디코더 블록당 한 번(MoE 모델) | moe (EP-ALLTOALL 둘러쌈) |
| `head` | 각 반복 끝에 한 번 | final_layernorm + lm_head + sampler |

`attention` 레이어는 항상 `pre_attn`과 `post_attn` 사이에 실행됩니다 — `sequence`에
없고 암묵적입니다.

## MoE 전용 YAML

MoE 아키텍처는 catalog에 `moe` 항목을 추가합니다:

```yaml
catalog:
  # ... dense 항목 ...
  moe:
    cls: FusedMoE
    category: moe
    ep_collective: ALLTOALL    # EP는 항상 ALLTOALL
```

그리고 `sequence`에:

```yaml
sequence:
  # ... dense와 동일 ...
  mlp_moe:
    - moe
  # MoE 모델에는 mlp_dense를 포함하지 말 것
```

시뮬레이터는 YAML에서 `mlp_moe`를 찾고, 존재하면 EP-ALLTOALL dispatch + combine
둘러쌈을 자동으로 실행합니다.

전체 MoE YAML은 `qwen3_moe.yaml`과 `mixtral.yaml`을 참고하세요.

## 단계별: 새 `model_type` 추가

`gemma2`(Google Gemma 2 시리즈)를 지원하고 싶다고 가정합시다. HF 설정에
`model_type: "gemma2"`가 있습니다. 워크플로우:

### 1. 모델의 vLLM 소스 검사

`vllm/model_executor/models/<model>.py`를 보세요. 식별할 것:

- 디코더 블록 클래스.
- 각 레이어 속성 이름(`self.qkv_proj`, `self.attention` 등).
- layernorm이 pre-attn / post-attn / 둘 다인지.
- 추가 레이어가 있는지(일부 모델은 post-MLP layernorm 등이 있음).
- MoE의 경우: expert가 어떻게 배열되는지.

### 2. `profiler/models/gemma2.yaml` 작성

가장 가까운 기존 YAML(예: Gemma 스타일 dense 모델은 `llama.yaml`)에서 시작하여
조정:

- `cls` 이름을 모델의 vLLM 클래스 이름과 일치하도록 업데이트.
- 추가 레이어(예: Gemma 2의 post-MLP layernorm)를 catalog와 `sequence`에 추가.
- 지연이 TP에 의존하지 않는 레이어에 `tp_stable: true` 설정.

### 3. 프로파일 시도

```bash
MODEL="google/gemma-2-9b" \
HARDWARE="<your-hw>" \
TP_DEGREES=1 \
SKIP_SKEW=1 \
./profiler/profile.sh
```

가장 빠른 피드백을 위해 TP=1과 `SKIP_SKEW=1`로 시작하세요. 프로파일러는:

- `sequence`의 레이어가 지정한 `cls`를 통해 모델에서 발견되지 않으면 크게 경고.
- 찾을 수 없는 레이어는 건너뜀(경고와 함께), 그래서 반복할 수 있음.

YAML이 맞으면 깔끔한 CSV를 얻습니다. 작은 시뮬레이션을 실행하여 확인하세요.

### 4. 시뮬레이션 시도

`cluster_config.json`에:

```json
{
  "model_name": "google/gemma-2-9b",
  "hardware": "<your-hw>",
  "tp_size": 1,
  ...
}
```

`python -m serving --cluster-config ... --dataset workloads/example_trace.jsonl ...`을
실행하세요.

무언가 잘못되면(레이어 미발견, 무한 루프, 누락된 collective), 시뮬레이터가 YAML의
어떤 레이어를 처리하는 법을 모르는지 알려줍니다. 고치고 재시도하세요.

### 5. 커밋 + PR 열기

동작하면 `profiler/models/gemma2.yaml`을 추가하는 PR을 보내세요. PR 제목을 `Add
gemma2 architecture support`로 하고 포함하세요:

- 검증에 사용한 HF 모델 id.
- smoke-test 시뮬레이션의 출력(작은 워크로드에 대한 TTFT / TPOT).
- MoE 테스트 여부(또는 아닌지 — Gemma 2는 MoE가 아니지만 다른 추가는 그럴 수 있음).

## `serving/core/trace_generator.py`도 건드려야 하는 때

YAML만으로는 표현할 수 없는 세 가지. 각각 작은 Python 추가가 필요합니다:

### Sliding-window attention

일부 모델(Mistral, sliding을 가진 Llama 3.1)은 어텐션을 고정 크기 윈도우로
제한합니다. 시뮬레이터의 KV-cache 예산이 이를 고려해야 합니다 — 총 KV가 윈도우
크기를 넘어 커지지 않음.

위치: `trace_generator.py`의 attention 카테고리 조회를 확장하여 `kv_decode`를 윈도우
크기에서 클립하고, `memory_model.py::get_kv`를 업데이트하여 요청당 KV 블록을 상한.

### MLA (Multi-Latent Attention, DeepSeek V3)

DeepSeek V3는 KV를 작은 latent로 압축하고 어텐션 시 압축 해제합니다. KV 크기가
`num_heads * head_dim * seq_len`이 시사하는 것보다 훨씬 작습니다.

위치: `memory_model.py::calculate_sizes`를 `num_kv_heads * head_dim` 대신 latent
차원(`kv_lora_rank`)을 사용하는 MLA 케이스로 확장.

### Dual MLP 디코더

일부 모델(예: 실험적 아키텍처)은 블록당 하나가 아니라 두 개의 MLP를 가집니다.
트레이스 생성이 블록당 두 개의 `mlp_dense` 실행을 생성해야 함을 알아야 합니다.

위치: 새 `sequence` 그룹(예: `mlp_dense_2`)을 추가하고
`trace_generator._emit_sequence`가 둘 다 따라가게 함.

이들은 모두 비교적 작은 변경(각 ~30–60 LOC)입니다. YAML + 기존 트레이스 생성기가
Python을 건드리지 않고 새 아키텍처의 95%를 처리합니다.

## 이것이 검증되는 곳

YAML이 들어가면, 번들된 `bench/` 검증 스위트가 sanity check입니다: 새 모델에 대해
vLLM을 end-to-end로 실행 + 같은 워크로드를 시뮬레이터로 실행 + 얼마나 가깝게
일치하는지 확인. TTFT / TPOT / throughput이 모두 ~5% 이내이면, YAML + (선택적)
trace_generator 변경이 좋습니다.

검증 방법론과 모델별 결과는 GitHub의
[`bench/README.md`](https://github.com/casys-kaist/LLMServingSim/tree/main/bench)를
참고하세요.

## 다음 단계

- **[출력 번들](./output-bundle)**: 동작하는 YAML이 주어졌을 때 프로파일러가
  생성하는 CSV.
- **[시뮬레이터 → 트레이스 생성](/docs/simulator/trace-generation)** — trace_generator가
  런타임에 `sequence:`를 따라가며 하는 일.
