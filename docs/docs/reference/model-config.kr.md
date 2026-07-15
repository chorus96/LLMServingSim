---
sidebar_position: 2
title: 모델 설정
---

# 모델 설정 스키마

모델 설정 파일은 `configs/model/<org>/<name>.json`에 있으며 **원본 HuggingFace
`config.json` 파일**입니다: `AutoModelForCausalLM`이 hub에서 다운로드할 바로 그
것입니다. 시뮬레이터와 프로파일러는 필드의 작은 부분집합만 읽고, 나머지는
무시합니다.

이 페이지는 중요한 부분집합을 문서화합니다.

## 파일 위치

모델별:

```
configs/model/
├── meta-llama/
│   └── Llama-3.1-8B.json
├── Qwen/
│   ├── Qwen3-32B.json
│   └── Qwen3-30B-A3B-Instruct-2507.json
└── ...
```

**[클러스터 설정](./cluster-config)**의 인스턴스 `model_name` 필드가
`configs/model/` 기준 상대 경로로 파일을 참조합니다.

파일이 없고 `model_name`이 HF id처럼 보이면, 프로파일러가 최초 실행 시 다운로드하여
캐시합니다. 시뮬레이터는 자동 다운로드를 **하지 않습니다**; 실행 전에 로컬 파일이
필요합니다.

## 필수 필드 (시뮬레이터가 읽는 부분집합)

| 필드 | 타입 | 사용처 | 설명 |
| --- | --- | --- | --- |
| `model_type` | string | 프로파일러 | `profiler/models/<model_type>.yaml`의 아키텍처 YAML을 선택. 예: `llama`, `qwen3`, `qwen3_moe`, `mixtral`, `phimoe` |
| `hidden_size` | int | 둘 다 | 모델 임베딩 / hidden 차원 |
| `num_hidden_layers` | int | 둘 다 | 디코더 블록 수 |
| `num_attention_heads` | int | 둘 다 | 총 어텐션 head(TP 스케일링용) |
| `num_key_value_heads` | int | 둘 다 | 구별되는 KV head(GQA 스케일링용) |
| `intermediate_size` | int | 둘 다 | MLP intermediate 차원 |
| `vocab_size` | int | 둘 다 | 임베딩 / `lm_head` 출력 차원 |
| `head_dim` | int | 둘 다 | **`hidden_size / num_attention_heads`가 아닌 경우 중요**(Qwen3은 명시적 `head_dim`을 가짐) |

`head_dim`이 설정에 없으면 시뮬레이터는 `hidden_size // num_attention_heads`로
폴백합니다. 이는 Qwen3에는 틀립니다(`head_dim: 128`, `hidden_size: 2048` /
`num_attention_heads: 32` → 64를 계산). HF 설정에 `head_dim`이 있는 모델은 항상
포함하세요.

## MoE 필드 (MoE 모델 전용)

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `num_local_experts` | int | 총 expert 수(Mistral 스타일: 예, Mixtral 8x7B의 `num_local_experts: 8`) |
| `num_experts` | int | 대체 명명(HF / Qwen 스타일: 예, Qwen3-30B-A3B의 `num_experts: 128`) |
| `num_experts_per_tok` | int | 토큰당 top-K 활성화. 일반적 값: 2(Mixtral), 8(Qwen3 MoE) |
| `moe_intermediate_size` | int | expert별 MLP intermediate 차원. 종종 dense `intermediate_size`보다 작음 |

시뮬레이터의 `config_builder.py`는 `num_local_experts`나 `num_experts` 중 하나를
받고 동등하게 취급합니다.

## 시뮬레이터가 소비할 수 있는 선택적 필드

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `torch_dtype` | string | 기본 가중치 dtype. `--dtype`가 전달되지 않을 때 사용. 예: `bfloat16`, `float16`, `float32` |
| `architectures` | array | 첫 항목의 클래스 이름은 정보용; 시뮬레이터는 `model_type`으로 디스패치 |
| `mlp_only_layers` | array | dense MLP(vs MoE)를 사용하는 레이어의 인덱스. Qwen3-MoE-Instruct 같은 하이브리드 MoE/dense 모델이 사용 |

## 시뮬레이터가 무시하는 필드

HF 설정에는 시뮬레이터가 사용하지 않는 훨씬 많은 필드가 있습니다 —
`bos_token_id`, `eos_token_id`, `attention_dropout`, `max_position_embeddings`,
`rope_*`, `rms_norm_eps`, `initializer_range`, `tie_word_embeddings` 같은 것들.
HF 설정 그대로 두세요; 무시되는 필드는 시뮬레이션에 영향을 주지 않습니다.

## 예제

### Llama 3.1 8B (dense)

```json
{
  "architectures": ["LlamaForCausalLM"],
  "model_type": "llama",
  "hidden_size": 4096,
  "intermediate_size": 14336,
  "num_attention_heads": 32,
  "num_hidden_layers": 32,
  "num_key_value_heads": 8,
  "vocab_size": 128256,
  "torch_dtype": "bfloat16"
}
```

(`head_dim`은 `4096 / 32 = 128`로 폴백되며, Llama 3.1에 올바릅니다.)

### Qwen3-32B (dense, 명시적 `head_dim`)

```json
{
  "architectures": ["Qwen3ForCausalLM"],
  "model_type": "qwen3",
  "hidden_size": 5120,
  "intermediate_size": 25600,
  "num_attention_heads": 64,
  "num_hidden_layers": 64,
  "num_key_value_heads": 8,
  "head_dim": 128,
  "vocab_size": 151936,
  "torch_dtype": "bfloat16"
}
```

(기본값은 `5120 / 64 = 80`이지만 Qwen3은 128을 사용. `head_dim`을 반드시 포함.)

### Qwen3-30B-A3B (MoE)

```json
{
  "architectures": ["Qwen3MoeForCausalLM"],
  "model_type": "qwen3_moe",
  "hidden_size": 2048,
  "intermediate_size": 6144,
  "num_attention_heads": 32,
  "num_hidden_layers": 48,
  "num_key_value_heads": 4,
  "head_dim": 128,
  "num_experts": 128,
  "num_experts_per_tok": 8,
  "moe_intermediate_size": 768,
  "vocab_size": 151936,
  "torch_dtype": "bfloat16"
}
```

## 새 모델 추가

1. 원본 HF `config.json`을 `configs/model/<org>/<name>.json`에 넣기.
2. 위의 필수 필드가 있는지 확인.
3. 모델의 HF 설정에 있으면 **`head_dim`을 명시적으로 추가**.
4. `profiler/models/<model_type>.yaml`이 존재하는지 확인. 없으면 새 아키텍처 YAML이
   필요합니다,
   **[프로파일러 → 모델 아키텍처 추가](/docs/profiler/adding-model-architecture)**
   참고.

## 함정

1. **`head_dim` 폴백은 조용합니다.** 포함하는 것을 잊었고 모델의 실제 `head_dim`이
   `hidden_size / num_attention_heads`와 다르면, 시뮬레이터는 실행되지만 잘못된
   KV-cache 크기를 계산합니다. HF 모델 카드에 대해 설정을 검증하세요.
2. **`num_local_experts` vs `num_experts`**: 같은 개념, 모델 계열마다 다른 명명
   규약. 모델의 HF 설정이 사용하는 쪽을 선택; 시뮬레이터는 둘 다 처리.
3. **`model_type`은 대소문자를 구분**하며 `profiler/models/<model_type>.yaml`의
   YAML과 정확히 일치해야 합니다.

## 다음 단계

- **[클러스터 설정](./cluster-config)**: `instances[].model_name`을 통해 모델 설정을
  참조.
- **[프로파일러 → 모델 아키텍처 추가](/docs/profiler/adding-model-architecture)** —
  새 `<model_type>.yaml`을 작성할 때.
