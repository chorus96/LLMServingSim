---
title: Continuous batching
sidebar_position: 1
---

# Continuous batching

스케줄러는 각 서빙 인스턴스의 심장입니다. 메인 루프의 모든 반복은
`scheduler.schedule(current, sys)`를 호출하고 `Batch`(또는 `None`)를 돌려받습니다.
스케줄러는 vLLM과 같은 제약을 강제합니다: 토큰 예산, 시퀀스 수 상한, 그리고
선택적으로 청크 프리필. 이 페이지는 그 규칙을 설명합니다.

> 설정 노브가 필요한가요? 플래그 목록은 **[레퍼런스 → CLI 플래그](/docs/reference/cli-flags)**를
> 참고하세요. 이 페이지는 *각 플래그가 내부적으로 무엇을 하는지* 설명합니다.

## 두 스케줄링 경로

`--enable-prefix-caching`(기본)이 켜졌는지에 따라, 스케줄러는
`serving/core/scheduler.py` 내부에서 두 코드 경로 중 하나를 취합니다:

| 플래그 | 메서드 | 무엇이 바뀌나 |
| --- | --- | --- |
| `--no-enable-prefix-caching` | `schedule_base` | 순수 토큰 예산 스케줄러. 각 요청이 항상 토큰 0부터 실행. |
| `--enable-prefix-caching`(기본) | `schedule_with_prefix` | 동일 + 요청별 `hit_len`을 반환하는 RadixCache 조회. |

두 경로 모두 제약은 동일합니다:

- **시퀀스 상한:** `len(batch) <= --max-num-seqs`. 기본 `128`. 무제한은 `0` 설정.
- **토큰 예산:** `sum(tokens_to_run_this_step) <= --max-num-batched-tokens`. 기본
  `2048`.
- **요청별 상한(청크 프리필):** `tokens_for_this_request_this_step <=
  --long-prefill-token-threshold`. 기본 `0` = 비활성화.

`schedule_with_prefix`는 추가로 인스턴스별 `MemoryModel.npu_prefix_cache`(RadixCache)를
유지합니다. 세부 사항은 **[Prefix caching](./prefix-caching)**.

## 스케줄러가 매 스텝 선택하는 것

```mermaid
flowchart TD
    START([반복 시작]) --> INIT[remaining_budget = max_num_batched_tokens<br/>batch = []]
    INIT --> NEXT{큐에 요청이<br/>더 있나?}
    NEXT -->|아니오| RETURN[Batch 또는 None 반환]
    NEXT -->|예| CAP{batch 크기<br/>>= max_num_seqs?}
    CAP -->|예| RETURN
    CAP -->|아니오| NEED[필요량 계산:<br/>prefill chunk 또는 decode 1 토큰]
    NEED --> MIN[cap = min remaining_budget,<br/>long_prefill_threshold,<br/>tokens_needed]
    MIN --> CHECKCAP{cap > 0?}
    CHECKCAP -->|아니오| NEXT
    CHECKCAP -->|예| MEM{eviction 후<br/>메모리 맞음?}
    MEM -->|아니오| NEXT
    MEM -->|예| ADD[batch에 추가<br/>budget -= cap]
    ADD --> NEXT
```

개념적으로 루프는:

```
remaining_token_budget = max_num_batched_tokens
batch = []
for request in queue (FIFO, 우선 시 prefill-first):
    if len(batch) >= max_num_seqs: break

    needs_to_run = how_many_tokens_this_request_needs(request)
    cap = min(remaining_token_budget,
              long_prefill_token_threshold or remaining_token_budget,
              needs_to_run)
    if cap <= 0:
        continue       # 다음 요청 시도

    schedule(request, tokens=cap)
    remaining_token_budget -= cap
    batch.append(request)

return Batch(batch) if batch else None
```

"이 요청이 필요로 하는 토큰 수" 함수는 요청 상태에 따라 다릅니다:

- **프리필, 아직 청크 없음:** 입력 길이에서 prefix cache 히트를 뺀 값.
- **프리필, 청크 중간:** 남은 프롬프트 토큰.
- **디코드:** 항상 1.

## 청크 프리필

`--long-prefill-token-threshold N`(또는 합리적 기본값을 설정하는
`--enable-chunked-prefill`)은 스케줄러가 긴 프리필을 여러 반복에 걸쳐 분할하게
합니다. 없으면 단일 32k 토큰 요청이 전체 예산을 독점하고 다른 진행 중 요청의
TPOT가 붕괴됩니다.

구체적으로, 남은 프리필이 8000 토큰인 요청은 `--long-prefill-token-threshold 1024`로
여덟 개의 스케줄러 반복에 걸쳐 8x1024 토큰 청크로 실행됩니다.
`Request.num_computed_tokens` 필드가 진행을 추적; 각 반복마다 스케줄러가 방금 처리된
토큰만큼 이를 올립니다.

디코드 스텝은 같은 배치에서 *동시에* 계속 실행되며, 청크 프리필은 단지 긴 프롬프트가
독점하는 것을 막습니다.

## 프리필 우선순위

기본적으로 프리필과 디코드 요청은 같은 FIFO 큐를 공유합니다. `--prioritize-prefill`로,
스케줄러가 배치를 재정렬하여 모든 프리필 요청이 먼저 오고, 그다음 디코드가 남은
예산을 채웁니다.

이는 버스트 도착 하에서 일부 TPOT를 더 낮은 TTFT와 교환합니다 — 사용자가 정상 상태
생성 속도보다 "첫 토큰 지연"을 더 신경 쓰는 배포에 유용합니다.

## 파이프라인 깊이 (PP)

`pp_size > 1` 인스턴스의 경우, 스케줄러는 현재 파이프라인을 통과 중인 배치의
`inflight` 리스트도 유지합니다. 그 길이는 `pp_size`로 상한됩니다: 파이프라인이
가득 차면, ASTRA-Sim이 스테이지를 비울 때까지 스케줄러가 `None`을 반환합니다.

이는 시뮬레이터의 PP 동작을 마이크로 배치가 파이프라인을 통과하는 프로덕션 학습
프레임워크(예: Megatron)와 일치시킵니다.

## 스케줄러가 멈추는 곳

시뮬레이터는 다음이 동시에일 때 종료합니다:

- 모든 스케줄러가 `None`을 반환(자격 있는 요청 없음).
- `Router.has_pending_requests()`가 `False`(미래 도착 없음).
- `Router.has_deferred_sessions()`가 `False`(도구 호출을 기다리는 agentic 세션 없음).

세 번째만 비어있지 않으면, 메인 루프가 `current`를 다음 대기 도착 시각으로 빨리
감고 재개합니다.

## 스케줄러가 돌려주는 것

`scheduler.add_done(npu_id, sys, current)`는 ASTRA-Sim이 완료를 보고할 때 반복당 한
번 호출됩니다. 반환:

```python
(prompt_throughput, decode_throughput, finished_requests)
```

- `prompt_throughput`는 **prefix cache 히트를 포함한 모든 입력 토큰**을 세며, (캐시된
  토큰도 세는) vLLM의 보고와 일치합니다. `decode_throughput`는 새로 생성된 토큰만
  셉니다.
- `finished_requests`는 이 반복 중 완료된 요청 리스트입니다.

P/D 분리 하의 프리필 인스턴스의 경우, 메인 루프가 `finished_requests`를
`router.transfer_prefill_request`에 넘겨 디코드 인스턴스가 이를 가져가게 합니다.

## 함정

1. **프리필 + prefix caching**은 이중 계수하지 않습니다: `hit_len`은 스케줄러가 실제로
   실행하는 토큰에서 빼지지만, `prompt_throughput`에는 *더해집니다*. 그래서 600 토큰의
   prefix 히트를 가진 1000 토큰 요청은 400 토큰의 예산을 소비하고 1000 토큰의 prompt
   throughput을 보고합니다.

2. **`--max-num-seqs 0`은 무제한**을 의미하지 0이 아닙니다. 순수 토큰 예산 게이팅을
   원할 때 유용하지만, 메모리를 주시하세요.

3. **토큰 예산은 프리필 + 디코드에 걸쳐 공유됩니다.** 진행 중 디코드 64개와 1500 토큰
   프리필 청크를 가진 배치는 이 스텝에 1564 토큰을 실행합니다. 디코드 기여가 계수됨.

4. **파이프라인 병렬화는 `inflight`를 `pp_size`로 상한합니다.** Chakra가 각 반복의
   레이어를 스테이지에 걸쳐 그 사이의 send/recv와 함께 분할하므로, 스테이지 간 P2P
   지연이 모델링됩니다.

## 다음 단계

- **[Prefix caching](./prefix-caching)**: `hit_len`이 무엇을 의미하며 RadixCache가
  어떻게 결정하는지.
- **[KV cache & 메모리](./kv-cache-and-memory)**: 스케줄러가 메모리가 가득 찼음을
  아는 방법.
