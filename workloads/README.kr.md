# workloads

`python -m serving --dataset <...>`와 `python -m bench run --dataset <...>`가
소비하는 요청 워크로드입니다. 정적 `.jsonl` 파일은 최상위에 위치하고,
`generators/` 하위 패키지가 필요 시 새 파일을 생성하며, `examples/` 폴더는
바로 수정해서 쓸 수 있는 실행 템플릿을 제공합니다.

## 레이아웃

```
workloads/
├── *.jsonl                    워크로드 파일 (flat 또는 agentic; 형식 참고)
├── generators/                JSONL 생성기
│   ├── __main__.py            python -m workloads.generators <name> ...
│   └── sharegpt.py            멀티턴 ShareGPT 파서 (tokenizer + 선택적 vLLM)
└── examples/                  바로 수정 가능한 모델별 실행 템플릿
    ├── gen-llama-3.1-8b.sh
    ├── gen-qwen3-30b-a3b.sh
    └── gen-qwen3-32b.sh
```

## 형식

데이터셋은 `.jsonl` 파일(한 줄에 JSON 객체 하나)로 저장됩니다. 두 가지 형식이 지원됩니다:

### Flat 요청 (예: ShareGPT)

각 줄은 독립적인 요청입니다:

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `input_toks` | Integer | 입력(프롬프트) 토큰 수 |
| `output_toks` | Integer | 출력(생성) 토큰 수 |
| `arrival_time_ns` | Integer | 요청 도착 시각(나노초) |
| `input_tok_ids` | List[Integer] | (선택) prefix cache 매칭을 위한 입력 시퀀스의 토큰 ID |
| `output_tok_ids` | List[Integer] | (선택) 출력 시퀀스의 토큰 ID |

```json
{"input_toks": 128, "output_toks": 512, "arrival_time_ns": 0, "input_tok_ids": [1, 2, 3]}
```

### Agentic 세션 (예: SWE-bench)

각 줄은 체인으로 연결된 LLM 호출들로 구성된 세션입니다. 시뮬레이터는 의존성
체인을 준수합니다: 각 하위 요청은 이전 요청이 완료되고 도구 실행 시간이
지난 후에만 제출됩니다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `session_id` | String | 고유한 세션 식별자 |
| `arrival_time_ns` | Integer | 세션 시작 시각(나노초) |
| `sub_requests` | List[Object] | 순서가 있는 LLM 호출 체인 |

각 하위 요청은 다음을 가집니다:

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `input_toks` | Integer | 이 LLM 호출의 입력 토큰 수 |
| `output_toks` | Integer | 이 LLM 호출의 출력 토큰 수 |
| `tool_duration_ns` | Integer | 이 호출 완료 후 다음 호출이 시작되기까지 대기하는 시간 (마지막은 0) |
| `input_tok_ids` | List[Integer] | (선택) prefix cache 매칭용 토큰 ID |
| `output_tok_ids` | List[Integer] | (선택) 출력의 토큰 ID |

```json
{
  "session_id": "task-0-run0",
  "arrival_time_ns": 4059740,
  "sub_requests": [
    {"input_toks": 1472, "output_toks": 133, "tool_duration_ns": 127348767},
    {"input_toks": 1582, "output_toks": 125, "tool_duration_ns": 0}
  ]
}
```

두 형식은 같은 파일에 공존할 수 있습니다. 형식은 `sub_requests` 키의 존재
여부로 자동 감지됩니다.

## 제공되는 데이터셋

### ShareGPT 트레이스

`python -m workloads.generators sharegpt --model <hf-id> --num-reqs <n> --sps <r>`로
필요 시 생성됩니다(`generators/` 참고). 출력 파일은 이 디렉터리에 바로 생성되며,
prefix-cache 해싱을 위해 `input_tok_ids`가 채워진 위의 flat 요청 형식을 따릅니다.


### SWE-bench agentic 트레이스
실제 SWE-bench 코딩 작업에서 파생된 agentic 세션으로, LLM 호출이 도구
호출(bash, grep, 파일 편집)로 체인 연결되어 있습니다. 각 세션은 도구 실행과
번갈아 가며 여러 LLM 하위 요청(세션당 6~20개)으로 구성된 완전한 코딩 작업입니다.

| 파일 | 세션 | 하위 요청 | 평균 하위 요청/세션 | 속도 (세션/s) | 모델 |
| --- | --- | --- | --- | --- | --- |
| `swe-bench-qwen3-30b-a3b-50-sps0.2.jsonl` | 50 | 765 | 15.3 | 0.2 | Qwen3-30B-A3B |

### 기타
| 파일 | 설명 |
| --- | --- |
| `example_trace.jsonl` | 빠른 테스트용 소형 예제 트레이스 |

## 워크로드 생성

워크로드는 `generators/` 하위 패키지로 생성됩니다. 이 패키지는 대상 모델의
토크나이저를 사용해 `input_tok_ids`를 채우고(그래서 prefix-cache 해시가
안정적임) 요청된 속도로 푸아송 분포 도착을 생성합니다. 기본 소스 데이터셋은
`shibing624/sharegpt_gpt4`(HF hub)이며, `--source`로 다른 HF id나 로컬 파일로
덮어쓸 수 있습니다.

가장 간단한 방법은 `examples/` 아래 템플릿 중 하나를 복사하여 필요에 따라
model / sps / num-reqs를 편집하고, vLLM Docker(`scripts/docker-vllm.sh`) 내부에서
실행하는 것입니다:

```bash
./workloads/examples/gen-qwen3-32b.sh
# 또는 명령줄에서 모델을 덮어쓰기:
MODEL="my-org/my-model" ./workloads/examples/gen-qwen3-32b.sh
```

임시(ad-hoc) 실행:

```bash
python -m workloads.generators sharegpt \
    --model Qwen/Qwen3-32B \
    --num-reqs 300 --sps 10 --seed 42 \
    --output workloads/sharegpt-qwen3-32b-300-sps10.jsonl \
    --use-vllm --vllm-tp 2 --vllm-dtype bfloat16
```

`--use-vllm`는 실제 vLLM `LLM` 엔진을 오프라인 배치 모드로 구동하여
`output_tok_ids`를 모델의 자연스러운 응답(자유 생성)으로 채웁니다. 이 옵션이
없으면 `output_tok_ids`는 ShareGPT 어시스턴트 턴에서 그대로 가져옵니다.

워크로드를 수동으로 만들려면, 위 형식을 따라 `.jsonl` 파일에 JSON 객체를
작성하고 `--dataset`으로 파일 경로를 `python -m serving` 또는
`python -m bench run`에 전달하세요.
