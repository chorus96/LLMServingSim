# configs/model

LLMServingSim이 알고 있는 모든 모델의 HuggingFace `config.json` 파일입니다.
**시뮬레이터**(메모리 모델 사이징, 레이어 카운팅, MoE 라우팅용)와
**프로파일러**(일치하는 아키텍처 yaml 선택 및 vLLM 공급용)가 공유합니다.

경로 규칙: `configs/model/<org>/<name>.json`은 HF 저장소 id를 반영합니다.
`meta-llama/Llama-3.1-8B.json`에 있는 파일은 `meta-llama/Llama-3.1-8B`를
기술합니다.

## 무엇이 들어가나

모델의 HuggingFace 저장소에서 가져온 원본 `config.json` 전체입니다. vLLM은
프로파일 시 임시 디렉터리를 통해 이를 직접 소비하므로, 파일에는 vLLM이
`load_format=dummy`로 모델을 인스턴스화하는 데 필요한 모든 필드가 있어야
합니다:

| 필드 | 용도 |
| --- | --- |
| `architectures` | vLLM이 이 목록에서 ForCausalLM 클래스를 선택 |
| `model_type` | 프로파일러가 일치하는 `profiler/models/<model_type>.yaml`을 선택 |
| `hidden_size`, `intermediate_size` | 선형 차원 |
| `num_attention_heads`, `num_key_value_heads` | 어텐션 형상 (GQA) |
| `num_hidden_layers` | 레이어 수 (시뮬레이터가 레이어당 시간에 이 값을 곱함) |
| `vocab_size`, `max_position_embeddings` | 임베딩 + 컨텍스트 |
| `head_dim` | `hidden_size ≠ num_attention_heads × head_dim`일 때 필요 (Qwen3) |
| `rms_norm_eps` / `layer_norm_eps` | Norm 설정 |
| `hidden_act` | MLP 활성화 함수 |
| `rope_theta`, `rope_scaling` | Rotary embedding 설정 (Llama 3의 rope_type에 중요) |
| `tie_word_embeddings` | lm_head가 임베딩과 가중치를 공유하는지 여부 |
| `attention_bias`, `mlp_bias` | 선형 레이어 bias |
| `torch_dtype` | 프로파일러가 이로부터 variant 폴더 이름을 자동 유도 |
| `num_local_experts` 또는 `num_experts`, `num_experts_per_tok`, `moe_intermediate_size` | MoE 전용 |

HF 저장소의 내용을 그대로 두세요 — 프로파일러 / 시뮬레이터는 필요 없는 키를
무시하므로 추가 필드가 있어도 무해합니다. 반드시 필요한 것은 `architectures`,
`model_type`, 그리고 차원 필드뿐입니다.

## 현재 제공되는 모델

| 파일 | 유형 | 레이어 | Hidden | Heads | KV | MoE |
| --- | --- | --- | --- | --- | --- | --- |
| `meta-llama/Llama-3.1-8B.json` | dense | 32 | 4096 | 32 | 8 | — |
| `meta-llama/Llama-3.1-70B.json` | dense | 80 | 8192 | 64 | 8 | — |
| `Qwen/Qwen3-32B.json` | dense | 64 | 5120 | 64 | 8 | — |
| `Qwen/Qwen3-30B-A3B-Instruct-2507.json` | MoE | 48 | 2048 | 32 | 4 | 128E / top-8 |
| `mistralai/Mixtral-8x7B-v0.1.json` | MoE | 32 | 4096 | 32 | 8 | 8E / top-2 |
| `microsoft/Phi-mini-MoE-instruct.json` | MoE | 32 | 4096 | 32 | 8 | 16E / top-2 |

## 새 모델 추가

세 가지 방법:

**1. 자동 다운로드 (가장 쉬움)** — `MODEL="<org>/<name>"`와 `HF_TOKEN`을
설정하고 프로파일러를 실행합니다. 설정이 로컬에 없으면 프로파일러가
HuggingFace hub에서 가져와 여기에 캐시합니다.

**2. Docker를 통한 수동 다운로드** — 컨테이너 내부에서:

```bash
python3 -c "
from huggingface_hub import hf_hub_download; import shutil
src = hf_hub_download(repo_id='google/gemma-2-9b', filename='config.json')
shutil.copyfile(src, '/workspace/configs/model/google/gemma-2-9b.json')
"
```

**3. 커스텀 모델 형상** — 프로파일하려는 차원으로 JSON을 직접 작성합니다.
`architectures`(vLLM용)와 `model_type`(프로파일러의 아키텍처 디스패치용)을
반드시 포함해야 합니다. 기존 설정 중 아무거나 동작하는 템플릿으로 쓸 수
있습니다:

```jsonc
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
  // … vLLM 모델 클래스가 기대하는 그 밖의 필드
}
```

예를 들어 `configs/model/custom/my-300b.json`으로 저장하고,
`profiler/profile.sh`에서 `MODEL="custom/my-300b"`를 설정한 뒤 실행하세요.
프로파일러가 이 설정을 vLLM에 직접 공급합니다.

## 아키텍처 지원

프로파일러는 `profiler/models/<model_type>.yaml`에 일치하는 아키텍처 yaml이
존재할 때만 실행됩니다. 현재 지원되는 `model_type` 값:

* `llama` — Llama 3.x 계열 (`Llama3RotaryEmbedding` 사용)
* `qwen3` — Qwen3 dense 계열
* `qwen3_moe` — Qwen3 MoE 계열
* `mixtral` — Mixtral 계열
* `phimoe` — Phi MoE 계열

그 밖의 `model_type`(예: `gemma2`, `deepseek_v3`)은 프로파일 시 지원 추가
방법을 안내하는 명확한 오류를 냅니다.
