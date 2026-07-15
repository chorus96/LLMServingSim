---
sidebar_position: 2
title: JSONL 형식
---

# JSONL 형식

워크로드 파일은 줄 구분 JSON(`.jsonl`)입니다. 각 줄은 독립적인 요청(flat 형식)
**또는** 체인으로 연결된 LLM 호출을 가진 세션(agentic 형식)을 나타내는 JSON
객체입니다. 두 형식은 같은 파일에 공존할 수 있으며, 로더가 줄마다 자동 감지합니다.

## Flat 형식

모든 줄은 하나의 독립적인 요청입니다:

```json
{"input_toks": 1472, "output_toks": 133, "arrival_time_ns": 4059740, "input_tok_ids": [1, 2, 3, ...], "output_tok_ids": [4, 5, 6, ...]}
```

### 필드

| 필드 | 타입 | 필수 | 의미 |
| --- | --- | --- | --- |
| `input_toks` | int | ✓ | 프롬프트 토큰 수 |
| `output_toks` | int | ✓ | 생성할 토큰 수 |
| `arrival_time_ns` | int | ✓ | 요청이 도착하는 시각(나노초, 시뮬레이션 시작 기준) |
| `input_tok_ids` | list&lt;int&gt; | 선택 | 사전 토큰화된 프롬프트 ID(prefix-cache 해싱 활성화, [아래](#why-token-ids-matter) 참고) |
| `output_tok_ids` | list&lt;int&gt; | 선택 | 사전 토큰화된 출력 ID(출력 측 분석에 내부적으로 사용; 보통 생략 가능) |

`input_tok_ids`가 제공되면 `len(input_tok_ids)`는 `input_toks`와 같아야 합니다(출력도
동일).

### 언제 flat을 사용하나

- ShareGPT 스타일 벤치마크(독립적 프롬프트).
- 프로덕션 트레이스 재실행(각 프롬프트가 자체 요청).
- 고정 푸아송 도착 패턴을 갖춘 스트레스 테스트.

## Agentic 형식

모든 줄은 여러 체인 연결된 LLM 호출을 가진 하나의 **세션**입니다. 각 호출의 도착
시각은 이전 호출의 완료와 그 사이의 `tool_duration_ns`로 결정되며, 시뮬레이터는 이
의존성 체인을 준수합니다:

```json
{
  "session_id": "session_0",
  "arrival_time_ns": 4059740,
  "sub_requests": [
    {"input_toks": 1472, "output_toks": 133, "tool_duration_ns": 127348767},
    {"input_toks": 1582, "output_toks": 125, "tool_duration_ns": 197295027},
    {"input_toks": 1734, "output_toks": 77,  "tool_duration_ns": 0}
  ]
}
```

### 최상위 필드

| 필드 | 타입 | 필수 | 의미 |
| --- | --- | --- | --- |
| `session_id` | string | ✓ | 세션의 고유 식별자 |
| `arrival_time_ns` | int | ✓ | **첫** 하위 요청이 도착하는 시각 |
| `sub_requests` | list&lt;object&gt; | ✓ | 순서가 있는 LLM 호출 체인. 길이 ≥ 1 |

### 하위 요청 필드

| 필드 | 타입 | 필수 | 의미 |
| --- | --- | --- | --- |
| `input_toks` | int | ✓ | 이 LLM 호출의 프롬프트 토큰 |
| `output_toks` | int | ✓ | 생성 토큰 |
| `tool_duration_ns` | int | ✓ | 이 호출 완료 **후** 다음 하위 요청이 자격을 얻기까지 대기 시간 |
| `input_tok_ids` | list&lt;int&gt; | 선택 | flat 형식과 동일 |
| `output_tok_ids` | list&lt;int&gt; | 선택 | flat 형식과 동일 |

마지막 하위 요청은 보통 `tool_duration_ns: 0`을 가집니다(세션 종료 후 기다릴 것
없음).

### 언제 agentic을 사용하나

- **도구를 사용하는 에이전트**(브라우저 에이전트, 코드 에이전트, 검색 단계를 갖춘 RAG).
- 각 세션이 여러 편집 + 테스트 + 재시도를 포함하는 **SWE-bench 스타일 벤치마크**.
- 턴 사이에 시뮬레이션된 사용자 사고 시간을 갖춘 **멀티턴 대화**.

시뮬레이터는 `Router._deferred_sessions`를 통해 체인을 처리합니다 — 처음에는 첫 하위
요청만 큐잉되고, 나머지는 선행 요청이 완료되면 방출됩니다. 런타임 메커니즘은
**[시뮬레이터 → 요청
생명주기](/docs/simulator/request-lifecycle#agentic-sessions-when-stage-10-is-not-the-end)**를
참고하세요.

## 형식 혼합

단일 `.jsonl` 파일은 flat과 agentic 항목을 모두 포함할 수 있습니다. 로더는 각 줄을
검사합니다:

- `sub_requests` 키가 있나? → agentic.
- 그렇지 않으면 → flat.

이는 때때로 유용합니다: agentic SWE-bench 워크로드가 sanity check를 위해 몇 개의
flat "베이스라인" 요청을 포함할 수 있습니다.

## 토큰 ID가 중요한 이유

선택적 `input_tok_ids` 필드는 prefix caching을 end-to-end로 동작하게 하는 것입니다:

- 이것이 없으면 시뮬레이터는 "프롬프트에 N개 토큰이 있다"는 것만 알고 두 프롬프트가
  prefix를 공유하는지 인식할 수 없습니다.
- 이것이 있으면 라우터가 로드 시 토큰 ID의 블록별 해시를 계산합니다. 스케줄러는 그
  해시를 사용하여 런타임에 요청을 RadixCache와 매칭합니다.

많은 요청이 system prompt를 공유하는 ShareGPT 스타일 트레이스의 경우, 토큰 ID가
있으면 prefix-cache 히트율이 없을 때보다 5~10배 높아집니다. **가능하면 사전
토큰화하세요.** 번들된 생성기가 이를 대신 해줍니다.

데이터셋에 원시 텍스트만 있으면 두 가지 옵션이 있습니다:

1. 워크로드 생성 시 토크나이저를 실행하여 `input_tok_ids`를 채우기. ShareGPT
   생성기가 이를 합니다.
2. 토큰 ID를 완전히 건너뛰기. `input_toks`만으로 *정확한* prefix 매칭에 대해 prefix
   caching이 여전히 동작하지만, 매칭이 훨씬 거칠고 대부분의 기회를 놓칩니다.

**시뮬레이터가 실행하는 것과 같은 모델로 토큰화하세요.** Llama 토크나이저로 생성된
워크로드는 Qwen3 시뮬레이션에서 유용한 prefix 히트를 만들지 못합니다 — 토큰 스트림이
전혀 다릅니다.

## 검증

로더(`router.load_requests`)는 시작 시 확인합니다:

- 모든 필수 필드가 존재.
- 제공되면 `len(input_tok_ids) == input_toks`(출력도 동일).
- `arrival_time_ns >= 0`이고 어떤 순서든 괜찮음 — 로더가 어차피 도착 시각으로 정렬.
- Agentic: 최소 하나의 하위 요청, `tool_duration_ns >= 0`.

검증 오류는 문제의 줄 번호와 필드 이름과 함께 출력되며; 로더는 시뮬레이션 작업이
시작되기 전에 종료합니다.

## 함정

1. **`arrival_time_ns`는 시뮬레이터 시계**이지 벽시계가 아닙니다. 초당 10 세션으로
   생성된 워크로드는 300 세션에 대해 30초에 걸친 도착 시각을 가지며, 이는 30
   시뮬레이터-초이지 30 실제 초가 아닙니다.
2. **토큰 ID는 문자열이 아니라 정수입니다.** 토크나이저가 출력하는
   것(`tokenizer.encode(...).ids`)이 여기에 바로 들어갑니다.
3. **출력 토큰 ID는 보통 런타임에 사용되지 않습니다**: 시뮬레이터는 디코드 타이밍을
   계산하는 데 필요하지 않습니다. 제공된 생성기는 다운스트림 분석 도구를 위해 이를
   포함합니다.
4. **워크로드 간 토크나이저 혼합은 괜찮지만, 한 파일 안에서 혼합은 안 됩니다.** 모든
   `input_tok_ids`는 같은 토크나이저에서 와야 합니다.

## 다음 단계

- **[ShareGPT 생성기](./sharegpt-generators)**: 적절한 토큰화와 함께 실제 ShareGPT
  트레이스에서 flat 워크로드를 생성.
- **[Agentic 세션](./agentic-sessions)**: agentic 형식과 자신의 체인을 구축하는
  방법에 대한 심층 설명.
