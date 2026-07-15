---
sidebar_position: 3
title: ShareGPT 생성기
---

# ShareGPT 생성기

ShareGPT는 사실상의 표준 추론 벤치마크로, 다양한 프롬프트 길이와 사용 사례에 걸친
실제 인간 ↔ ChatGPT 대화의 큐레이션 데이터셋입니다. 번들된 생성기는
ShareGPT(또는 호환되는 Hugging Face 텍스트 데이터셋)를 시뮬레이터가 소비하는 JSONL
형식으로 변환하며, prefix caching을 위한 적절한 토큰화를 포함합니다.

## 빠른 실행

`/workspace`의 vLLM Docker 컨테이너에서:

```bash
python -m workloads.generators sharegpt \
  --model meta-llama/Llama-3.1-8B \
  --source shibing624/sharegpt_gpt4 \
  --num-reqs 300 --sps 10 --seed 42 \
  --output workloads/sharegpt-llama-3.1-8b-300-sps10.jsonl
```

이는 평균 초당 10 세션으로 도착하는 300개 요청의 flat 형식 워크로드를
Llama-3.1-8B 토크나이저로 토큰화하여 생성합니다.

`workloads/examples/`에는 번들된 모델을 위한 바로 수정 가능한 템플릿이 있습니다.
복사하여 조정하세요:

```bash
ls workloads/examples/
# gen-llama-3.1-8b.sh
# gen-qwen3-30b-a3b.sh
# gen-qwen3-32b.sh
```

## vLLM 컨테이너를 사용하는 이유

생성기는 토큰화를 위해 `transformers`를, (선택적으로) 자유 생성 모드를 위해
`vllm`을 임포트합니다. 둘 다 vLLM Docker 이미지에 사전 설치되어 있습니다.
`scripts/docker-vllm.sh` 내부에서 실행하면 Python 의존성을 직접 관리할 필요가
없습니다.

게이트된 모델(Llama 3.x 등)의 경우, 컨테이너 실행 전에 `HF_TOKEN`을 설정하세요.
**[설치 → vLLM 설정](/docs/getting-started/installation/vllm)**을 참고하세요.

## 옵션, 그룹별

### 소스와 모델

| 플래그 | 기본값 | 의미 |
| --- | --- | --- |
| `--model` | (필수) | HuggingFace 모델 id; 토큰화(및 선택적 자유 생성)에 사용 |
| `--source` | `shibing624/sharegpt_gpt4` | HF 데이터셋 id 또는 로컬 경로. `conversations` 필드를 가진 데이터셋이면 동작 |

### 샘플링

| 플래그 | 기본값 | 의미 |
| --- | --- | --- |
| `--num-reqs` | (필수) | 생성할 요청 / 세션 수 |
| `--sps` | (필수) | 시뮬레이션 초당 세션(푸아송 도착) |
| `--seed` | `42` | 샘플링과 도착 시각을 위한 RNG 시드 |
| `--first-arrival-sec` | `0` | 첫 요청 도착 시각의 오프셋 |

### 길이 필터

소스 데이터셋에서 이 범위 밖의 요청을 버립니다:

| 플래그 | 기본값 | 의미 |
| --- | --- | --- |
| `--min-input-toks` | `0` | 최소 프롬프트 토큰(토큰화 후) |
| `--max-input-toks` | `16384` | 최대 프롬프트 토큰 |
| `--min-output-toks` | `0` | 최소 출력 토큰 |
| `--max-output-toks` | `16384` | 최대 출력 토큰 |
| `--max-kv-toks` | `16384` | `input + output` 토큰 상한(KV-cache 풋프린트) |
| `--max-sessions` | `5000` | 필터링 전 샘플링되는 소스 세션 수 상한 |

합리적인 시작점: `--min-input-toks 256 --min-output-toks 512`는 실제 서빙 트래픽을
대표하지 않는 매우 짧은 대화를 걸러냅니다.

### 고정 길이 모드

제어된 스트레스 테스트를 위해 프롬프트와 출력 길이를 고정:

| 플래그 | 기본값 | 의미 |
| --- | --- | --- |
| `--fix-len` | off | 고정 길이 모드 활성화 |
| `--fix-input-length` | `128` | 프롬프트 토큰 |
| `--fix-output-length` | `512` | 출력 토큰 |

이 모드에서 생성기는 prefix-cache 현실성을 위해 여전히 소스 데이터셋에서 실제
대화를 가져오지만, 각각을 고정 길이로 절단 / 패딩합니다.

### Pulse 도착 패턴

"모두가 정시에 API를 친다"는 프로덕션 현상을 근사하는 버스트 모드 도착 패턴:

| 플래그 | 기본값 | 의미 |
| --- | --- | --- |
| `--pulse` | off | Pulse 모드 활성화 |
| `--pulse-n` | `10` | pulse당 요청 수 |
| `--pulse-delay-sec` | `60` | pulse 사이의 시간 |
| `--pulse-poisson` | off | 각 pulse 내에서 한꺼번에가 아니라 설정된 `--sps`로 푸아송 도착 사용 |

`--pulse-poisson` 없이는 pulse 도착이 각 pulse 윈도우 시작에 모두 발사됩니다 —
시뮬레이터의 버스트 처리 동작을 테스트하는 데 유용합니다.

### vLLM 자유 생성 모드 (선택)

출력 토큰에 소스 데이터셋의 응답 필드를 사용하는 대신, vLLM으로 출력을
**재생성**합니다. 이는 시뮬레이터에서 실행할 모델과 일치하는 출력을 생성합니다:

| 플래그 | 기본값 | 의미 |
| --- | --- | --- |
| `--use-vllm` | off | vLLM을 사용하여 출력을 자유 생성 |
| `--vllm-tp` | `1` | vLLM의 TP 차수 |
| `--vllm-dtype` | `bfloat16` | vLLM 가중치 dtype |

`--use-vllm`으로:

1. 프롬프트는 ShareGPT에서 가져옴.
2. vLLM이 그 모델로 새 응답을 생성.
3. 프롬프트와 응답 모두 토큰화됨; `input_tok_ids`와 `output_tok_ids`가 채워짐.

`--use-vllm` 없이:

- 프롬프트와 응답 모두 ShareGPT 항목에서 텍스트로 옴.
- `input_tok_ids`를 위해 프롬프트만 `--model`의 토크나이저로 재토큰화됨.

출력 토큰 ID가 모델이 실제로 생성할 것과 일치하기를 특별히 원할 때 `--use-vllm`을
사용하세요. 대부분의 시뮬레이터 실행에는 필요하지 않지만(시뮬레이터는 텍스트를
생성하지 않고 토큰만 셈), 다운스트림 평가나 완전히 자기 일관적인 트레이스를 원할
때 유용합니다.

## 출력 형식

생성기는 요청당 하나의 JSONL 줄을 씁니다:

```json
{"input_toks": 1472, "output_toks": 133, "arrival_time_ns": 4059740, "input_tok_ids": [...], "output_tok_ids": [...]}
```

항상 **flat 형식**: ShareGPT 항목은 의존성 체인이 없습니다. agentic 워크로드는
**[Agentic 세션](./agentic-sessions)**을 참고하세요.

출력 파일 이름 규약은 `sharegpt-<model-short>-<n>-sps<rate>.jsonl`입니다(번들된
파일과 일치).

## 팁

1. **시뮬레이터가 실행할 것과 같은 모델로 토큰화하세요.** 그렇지 않으면 시뮬레이터의
   prefix-cache 히트율이 프로덕션이 보는 것과 일치하지 않습니다. 번들된 JSONL
   파일은 이 규약을 사용하며 각 모델과 짝지어져 있습니다.
2. **`--max-sessions`는 출력이 아니라 소스 샘플에 상한을 둡니다.** 타이트한 길이
   필터를 적용하는데 살아남는 요청이 충분하지 않으면 늘리세요. 기본 5000은 대부분의
   `--num-reqs` 값에 충분합니다.
3. **Pulse 모드는 sanity 테스트에 훌륭합니다.** 깔끔한 버스트 패턴은 부드러운 푸아송
   도착이 숨길 수 있는 스케줄러 동작(큐 축적, 공정성, head-of-line blocking)을
   드러냅니다.
4. **생성 속도.** `--use-vllm` 없이는 생성이 토큰화 바운드이며 몇 초에 끝납니다.
   `--use-vllm`으로는 실제 vLLM 추론 비용을 지불하며, `--num-reqs`에 따라 몇 분에서
   몇 시간. 출력 JSONL을 캐시하세요.
5. **시뮬레이터 실행 전반에 JSONL을 재사용하세요.** 한 번 생성하고 여러 번
   시뮬레이션. 파일은 작고(~MB) 독립적입니다.

## 다음 단계

- **[JSONL 형식](./jsonl-format)**: 생성기가 생성하는 것의 스키마 레퍼런스.
- **[Agentic 세션](./agentic-sessions)**: 폐루프 워크로드용. ShareGPT 생성기는 flat
  워크로드만 생성합니다.
