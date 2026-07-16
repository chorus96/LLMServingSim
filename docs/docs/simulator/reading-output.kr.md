---
title: 출력 읽기
sidebar_position: 8
---

# 출력 읽기

시뮬레이터는 세 종류의 출력을 생성합니다:

1. `--output`으로 전달된 경로의 **요청별 CSV**.
2. `--log-interval` 초마다 출력되는 **throughput 로그 라인**.
3. **최종 전력 요약**(클러스터 설정에 `power:` 블록이 있는 경우에만).

이 페이지는 각각이 무엇을 의미하며 어떻게 읽는지 다룹니다.

## 요청별 CSV

`--output outputs/foo.csv`를 전달하면, 시뮬레이터가 완료된 요청당 한 행을 씁니다:

```csv
instance id,request id,model,input,output,arrival,end_time,latency,queuing_delay,TTFT,TPOT,ITL
0,0,Qwen/Qwen3-30B-A3B-Instruct-2507,1472,133,4059740,1082836204,1078776464,0,51162321,7784955,"[7780422, 7779379, 7779523, ...]"
0,3,meta-llama/Llama-3.1-8B,4,16,570907776,711600111,140692335,3739551,15137413,11414083,"[11043655, 11381158, ...]"
...
```

번들된 `outputs/example_*_run.csv` 파일(`serving/run.sh`의 시나리오당 하나)이 훑어보기
좋은 예제입니다.

### 열 레퍼런스

| 열 | 타입 | 의미 |
| --- | --- | --- |
| `instance id` | int | 이 요청을 실행한 서빙 인스턴스 |
| `request id` | int | 라우터가 할당한 단조 증가 id |
| `model` | string | 모델 이름(예: `meta-llama/Llama-3.1-8B`) |
| `input` | int | 프롬프트 토큰(prefix-cache 히트 포함 전체 입력 길이) |
| `output` | int | 생성된 디코드 토큰(즉, 전체 길이에서 `input`을 뺀 값) |
| `arrival` | int (ns) | 요청 도착 시각(시뮬레이터 시계) |
| `end_time` | int (ns) | 마지막 생성 토큰이 완료된 시각 |
| `latency` | int (ns) | End-to-end 지연: `end_time - arrival` |
| `queuing_delay` | int (ns) | 도착에서 첫 스케줄링 스텝까지 |
| `TTFT` | int (ns) | Time-to-first-token: 첫 토큰 완료 시각에서 `arrival`을 뺀 값 |
| `TPOT` | int (ns) | 평균 출력 토큰당 시간: `(latency - TTFT) // (output - 1)`(또는 `output == 1`일 때 `0`) |
| `ITL` | string | 토큰 간 지연, ns. 직렬화된 Python 리스트, 예: `"[7780422, 7779379, ...]"` |

모든 시간은 **나노초** 단위입니다. 초는 `1e9`로, 밀리초는 `1e6`으로 나누세요. 열
이름은 언더스코어가 아니라 공백을 사용; pandas에서 인용하세요(`df["instance id"]`).

> **참고:** `Request` 객체는 내부적으로 `session_id` / `sub_request_index`(agentic
> 워크로드용)와 계층별 prefix-cache 히트 카운터(`prefix_cache_hit`, `npu_cache_hit`,
> `storage_cache_hit`)도 담습니다. 이들은 메모리에서 추적되고 throughput 로그
> 라인에 표시되지만, 오늘 요청별 CSV에는 기록되지 **않습니다**. 집계 prefix-히트율을
> 보려면 throughput 로그(`--log-interval`)를 사용하세요; 요청별 agentic 회계를 위해서는
> `Request` 객체를 직접 읽거나 `Scheduler.save_output`을 확장하세요.

### 흔한 유도 지표

```python
import pandas as pd
df = pd.read_csv("outputs/foo.csv")

# 밀리초 단위 벽시계 TTFT
df["TTFT_ms"] = df["TTFT"] / 1e6

# 밀리초 단위 TPOT(이미 토큰당 평균; ms로 나눔)
df["TPOT_ms"] = df["TPOT"] / 1e6

# 초 단위 end-to-end 지연
df["latency_s"] = df["latency"] / 1e9

# 전체 실행에 걸친 throughput(토큰 / 초)
total_tokens = (df["input"] + df["output"]).sum()
sim_duration_s = (df["end_time"].max() - df["arrival"].min()) / 1e9
throughput = total_tokens / sim_duration_s

# 인스턴스별 분포
per_inst = df.groupby("instance id").agg(
    requests=("request id", "count"),
    p50_TTFT_ms=("TTFT", lambda x: x.quantile(0.5) / 1e6),
    p99_TTFT_ms=("TTFT", lambda x: x.quantile(0.99) / 1e6),
)

# 토큰 간 지연: ITL 문자열을 행별 리스트로 다시 파싱
import ast
df["ITL_list"] = df["ITL"].apply(ast.literal_eval)
df["ITL_p50_ms"] = df["ITL_list"].apply(lambda xs: pd.Series(xs).quantile(0.5) / 1e6)
```

## 표준 출력 (로그 레벨)

시뮬레이터의 `--log-level` 플래그는 실행 진행 중 stdout에 얼마나 많은 세부 사항이
나오는지 제어합니다:

| 레벨 | 보이는 것 |
| --- | --- |
| `WARNING`(기본) | `--log-interval` 초마다 throughput 로그 라인, 그리고 경고(variant 폴백, 런타임이 프로파일러 스윕 초과, MoE 설정 불일치 등) |
| `INFO` | 반복별 스케줄러 결정(어떤 요청이 배치에 들어갔는지, 요청별 prefix-cache 히트)과 요청 생명주기(도착 / 첫 토큰 / 완료)를 추가. 라우팅과 스케줄링 디버깅에 유용. |
| `DEBUG` | 레이어별 메모리 load / store 활동, 전체 `Batch` / `Request` 덤프, `npu_prefix_cache.format_prefix_info()` 스냅샷을 추가. 많은 출력을 생성; 파일로 파이프하세요. |

레벨과 무관하게, 시뮬레이터는 항상 방출합니다:

- 해석된 `(hardware, model, variant)`와 `meta.yaml` 대비 engine_effective 비교를 가진
  시작 배너.
- 종료 시 최종 요약(총 요청, 평균 TTFT / TPOT, throughput, 그리고 `power:`가 설정되면
  아래의 **전력 요약**).

throughput 로그 라인 자체는 레벨과 무관하게 동일합니다 — 유일한 차이는 그것을 둘러싼
것입니다.

## Throughput 로그 라인

`--log-interval` 초마다 시뮬레이터가 한 줄 상태 업데이트를 출력합니다. 형식은 어떤
기능이 활성화되었는지에 적응합니다:

### 단일 인스턴스 베이스라인

```text
[INFO] step=42 batch=8 prompt_t=1.2k tok/s decode_t=420 tok/s npu_mem=88.4 GB
```

| 필드 | 의미 |
| --- | --- |
| `step` | 이 간격이 끝난 반복 번호 |
| `batch` | 요청 단위 배치 크기 |
| `prompt_t` | 프롬프트 측 throughput(입력 토큰/초, prefix 히트 포함) |
| `decode_t` | 디코드 측 throughput(생성 토큰/초) |
| `npu_mem` | 이 순간의 NPU 메모리 풋프린트 |

### 다중 인스턴스

```text
[INFO] step=21 inst0_batch=6 inst1_batch=4 prompt_t=2.5k tok/s decode_t=860 tok/s
       npu_mem=[63.2 GB, 63.2 GB]
```

`inst0_batch` / `inst1_batch`는 인스턴스별 배치 크기; `npu_mem`은 인스턴스별.

### 프리필 / 디코드 분리

```text
[INFO] step=15 P=8 D=12 prompt_t=3.1k tok/s decode_t=620 tok/s
       npu_mem=[55.4 GB, 71.2 GB]
```

`P=`와 `D=`는 프리필 및 디코드 인스턴스의 배치 크기.

### Prefix 공유 포함

```text
[INFO] step=20 inst0_batch=6 inst1_batch=4 prompt_t=2.4k tok/s decode_t=820 tok/s
       prefix_hit=78% (npu=42%, cpu=36%)
```

`prefix_hit` 필드는 간격에 걸친 cache 히트율을 계층별로 나누어 보여줍니다.

### DP+EP MoE 포함

```text
[INFO] step=8 batch=4+4 prompt_t=1.4k tok/s decode_t=520 tok/s
       npu_mem=[81.2 GB, 81.2 GB] alltoall=512 KB
```

`batch=4+4`는 DP 멤버별 배치를 보여줌. `alltoall`은 wave-synchronized ALLTOALL 메시지
크기.

### PIM offload 포함

```text
[INFO] step=10 batch=8 prompt_t=1.1k tok/s decode_t=520 tok/s
       npu_mem=63.4 GB pim_busy=72%
```

`pim_busy`는 PIM 장치가 활성이었던 간격의 비율. ~100%면 PIM이 병목입니다.

### CXL 메모리 포함

```text
[INFO] step=10 batch=4 prompt_t=620 tok/s decode_t=180 tok/s
       npu_mem=12.4 GB cxl_mem=[3.2 GB, 3.1 GB, 3.1 GB, 3.2 GB]
```

`cxl_mem`은 장치별 사용량; 가중치가 CXL에 있어 `npu_mem`이 떨어짐.

### 전력 모델 포함

```text
[INFO] step=42 batch=8 prompt_t=1.2k tok/s decode_t=420 tok/s
       npu_mem=88.4 GB power=712 W
```

`power`는 **현재** 총 시스템 전력.

## 최종 전력 요약

`--output`이 설정되고 클러스터 설정에 `power:` 블록이 있으면, 시뮬레이터가 끝에
노드별 에너지 분석을 방출합니다:

```text
─────── Power summary (node 0) ───────
   NPU active     :   12,453 J  (78%)
   NPU standby    :    1,012 J   (6%)
   NPU idle       :       89 J   (1%)
   CPU            :    1,233 J   (8%)
   DRAM           :      442 J   (3%)
   Link           :      388 J   (2%)
   Base + NIC + storage : 332 J  (2%)
   ─────────────────────────────────
   Total energy   :   15,949 J
```

다중 노드 실행의 경우 노드당 하나의 블록과 클러스터 총계를 얻습니다. 이 분석이 전력
수치를 에너지 효율성 연구에 실행 가능하게 만듭니다 — 어떤 구성 요소가 지배하는지 볼
수 있습니다.

## 찾아볼 흔한 패턴

### 높은 waiting 수, 낮은 NPU 메모리

throughput 로그가 큰 `batch` 수를 보여주지만 `npu_mem`이 클러스터 설정의
`npu_mem.mem_size`보다 훨씬 낮음. 유력한 원인: 메모리가 아니라 토큰
예산(`--max-num-batched-tokens`)이 병목. 올리세요.

### 프리필 버스트 중 디코드 TPOT 급증

프리필 위주 순간이 진행 중 디코드와 같은 배치에 도착하고, 예산이 프리필에 먹히며,
디코드 지연이 늘어남.

완화:
- `--enable-chunked-prefill`(기본)이 긴 프리필을 분할.
- `--long-prefill-token-threshold N`이 스텝당 프리필 토큰을 상한.
- `--prioritize-prefill`이 예산 내에서 프리필을 먼저 실행, TPOT를 TTFT와 교환.

### Prefix 히트율이 0% 근처

워크로드에 정말로 공유 prefix가 없거나, 사전 토큰화를 잊었음. JSONL에
`input_tok_ids`가 채워졌는지 확인하세요([워크로드 → JSONL
형식](/docs/workloads/jsonl-format) 참고).

### MoE 랭크별 지연이 크게 변동

`--expert-routing-policy BALANCED`(기본)를 설정하세요. RR이나 RAND는 작은 배치에서
고르지 않은 부하를 생성할 수 있습니다. BALANCED로, 랭크별 지연이 ~1% 이내로
균일해야 합니다.

### CXL 지연이 TPOT를 지배

CXL에 배치된 가중치는 매 디코드 스텝에 왕복을 지불합니다. TPOT가 예상보다 훨씬
나빠 보이면, `placement` 블록을 확인하세요 — cold 레이어(embedding, lm_head)를 CXL로
옮기는 것은 도움이 됨; 모든 디코더 블록을 옮기는 것은 해로움.

## 알려진 참조에 대한 검증

LLMServingSim은 번들된 하드웨어 × 모델 조합에서 TTFT / TPOT / throughput에 대해 3%
미만 오차로 실제 vLLM과 end-to-end로 검증됩니다. 검증 방법론과 모델별 결과는 GitHub의
**[bench/](https://github.com/casys-kaist/LLMServingSim/tree/main/bench)**에 있습니다.

## 다음 단계

- **[레퍼런스 → CLI 플래그](/docs/reference/cli-flags)**: 출력에 영향을 주는 모든
  플래그.
- **[예제](/docs/examples)**: 출력을 비교할 작동 설정.
