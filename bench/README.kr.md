# bench

End-to-end vLLM 벤치마크 + 시뮬레이터 검증. 실제 vLLM 서빙 워크로드를 실행하고,
요청별 타이밍과 틱별 스케줄러 상태를 캡처한 뒤, 동일한 데이터셋에 대한
시뮬레이터의 출력과 결과를 비교합니다.

## 레이아웃

```
bench/                          Python 패키지 — `python -m bench ...`
├── __init__.py                 패키지 마커 + 모듈 맵
├── __main__.py                 CLI 디스패치 (run / validate)
├── core/                       내부 구현
│   ├── runner.py               AsyncLLM 드라이버, RequestStateStats 캡처
│   ├── recorder.py             meta.json / requests.jsonl / timeseries.csv 기록
│   ├── stat_logger.py          timeseries를 채우는 커스텀 vLLM StatLoggerBase
│   ├── validate.py             bench-vs-sim 비교 진입점
│   ├── plots.py                throughput / running-waiting / latency-CDF 헬퍼
│   └── logger.py               Rich 기반 로거 + stdio 캡처
├── bench.sh                    호스트 측 ``python -m bench run`` 래퍼
├── validate.sh                 호스트 측 ``python -m bench validate`` 래퍼
├── examples/                   대표적인 end-to-end 실행 (커밋된 산출물)
│   ├── configs/<model>.json    시뮬레이터 측이 사용하는 클러스터 설정
│   ├── <model>/vllm/           vLLM 벤치 산출물 (meta.json, requests.jsonl, timeseries.csv)
│   ├── <model>/outputs/        시뮬레이터 출력 (sim.csv, sim.log)
│   ├── <model>/validation/     `bench validate` 출력 (PDF + summary.txt)
│   ├── run.sh                  임의/전체 예제에 대해 시뮬레이터 측 재실행
│   └── validate.sh             임의/전체 예제에 대해 검증 단계 재실행
└── results/                    임시 실행의 출력 루트: bench/results/<run_id>/
```

## 사용법

`bench run` — 기존 데이터셋의 엄격한 재실행(replay)

러너는 LLMServingSim 형식의 JSONL(`python -m workloads.generators`가 생성하고
`python -m serving --dataset`가 소비하는 동일한 형식)을 읽습니다. 각 요청의
`input_tok_ids`와 `output_toks`는 `SamplingParams(min_tokens=N, max_tokens=N,
ignore_eos=True)`로 고정되므로, vLLM 실행은 동일 워크로드에 대한 시뮬레이터의
관점과 비트 단위로 비교 가능합니다.

```bash
# vLLM 컨테이너(scripts/docker-vllm.sh) 내부에서.
./bench/bench.sh
# 또는 명시적 인자로 모듈을 직접 호출:
python -m bench run \
    --model <hf-id-or-path> \
    --dataset workloads/<workload>.jsonl \
    --output-dir bench/results/<run_id> \
    --tensor-parallel-size 1 --data-parallel-size 1 \
    --max-num-seqs 128 --max-num-batched-tokens 2048 \
    --dtype bfloat16 --kv-cache-dtype auto
```

`bench validate` — 완료된 bench 실행을 시뮬레이터 출력과 비교

동일 워크로드에 대한 bench 산출물과 시뮬레이터의 `sim.csv` / `sim.log`를
로드하여, 일치하는 정의 하에 양쪽에서 TTFT / TPOT / end-to-end 지연 시간을
계산하고, 플롯 + 수치 요약을 bench 실행의 하위 디렉터리에 기록합니다.

```bash
./bench/validate.sh \
    bench/results/<run_id> \
    outputs/<sim-run>/sim.csv \
    outputs/<sim-run>/sim.log \
    [prefix]
```

## 출력 스키마 (하나의 bench 실행)

```
bench/results/<run_id>/
  meta.json            실행 메타데이터 (model, vLLM 버전, 엔진 kwargs,
                       데이터셋 해시, 벽시계 시작/종료)
  requests.jsonl       요청별 타이밍 — request_id, input_toks,
                       output_toks, arrival_time, queued_ts, scheduled_ts,
                       first_token_ts, last_token_ts
  timeseries.csv       틱별 집계 — t, prompt_throughput,
                       gen_throughput, running, waiting, kv_cache_pct
  validation/          (`bench validate`가 생성)
    <prefix>_throughput.png
    <prefix>_requests.png
    <prefix>_latency.png
    <prefix>_summary.txt
```

## 지연 시간 정의 (sim ↔ bench)

diff%가 의미 있도록 양쪽 모두 동일한 기준점에서 TTFT, TPOT, end-to-end
지연 시간을 보고합니다:

| 지표 | 정의 |
| --- | --- |
| `TTFT`     | `first_token_ts - arrival_time` (큐잉 포함) |
| `TPOT`     | `(last_token_ts - first_token_ts) / max(1, output_toks - 1)` |
| `Latency`  | `last_token_ts - arrival_time` |

시뮬레이터의 `sim.csv`는 `arrival`, `end_time`, 토큰별 ITL 리스트를 직접
노출합니다. bench는 vLLM의 `RequestStateStats`(`vllm/v1/metrics/stats.py`)에서
동일한 필드를 계산합니다.

## 대표 예제 (`bench/examples/`)

`bench/examples/` 아래에 dense 단일 GPU 베이스라인, TP=2 dense 실행, DP+EP MoE
실행을 다루는 세 개의 end-to-end 검증 실행이 커밋되어 있습니다. 각 예제는
vLLM 벤치 산출물, 시뮬레이터 출력, 그리고 결과 `bench validate` 요약 + 플롯을
함께 묶습니다.

| 예제 | 병렬화 | 워크로드 (300 요청) | TTFT 평균 | TPOT 평균 | Latency 평균 |
| --- | --- | --- | --- | --- | --- |
| `Llama-3.1-8B`                | TP=1 dense              | `sharegpt-llama-3.1-8b-300-sps10.jsonl`     | -2.8% | -0.3% | -1.0% |
| `Qwen3-32B`                   | TP=2 dense              | `sharegpt-qwen3-32b-300-sps10.jsonl`        | -0.7% | -0.3% | -0.4% |
| `Qwen3-30B-A3B-Instruct-2507` | DP=2, EP=2 MoE          | `sharegpt-qwen3-30b-a3b-300-sps10.jsonl`    | -2.9% | +0.6% | +0.4% |

diff%는 `(sim - vLLM) / vLLM × 100`입니다. 세 실행 모두 RTXPRO6000에서 `bf16`
가중치, `max_num_seqs=128`, `max_num_batched_tokens=2048`, `block_size=16`으로
수행되며, 워크로드는 `python -m workloads.generators`(ShareGPT, 싱글턴, vLLM
자유 생성 모드)로 생성됩니다. 백분위별 분석(P50 / P90 / P95 / P99)은 각
`bench/examples/<model>/validation/summary.txt`에 있습니다.

대표 예제 재현:

```bash
# 시뮬레이터 컨테이너 내부에서:
./bench/examples/run.sh                       # 세 예제 모두
./bench/examples/run.sh Qwen3-30B-A3B-Instruct-2507   # 단일 예제

# 그런 다음 커밋된 vLLM 산출물과 비교 검증:
./bench/examples/validate.sh
./bench/examples/validate.sh Qwen3-30B-A3B-Instruct-2507
```

`run.sh`는 각 예제의 `meta.json`(엔진 kwargs + 데이터셋 경로)과
`bench/examples/configs/` 아래의 일치하는 클러스터 설정을 읽으므로,
시뮬레이터는 원본 vLLM 벤치와 정확히 동일한 워크로드 및 엔진 설정으로
실행됩니다. vLLM 측을 처음부터 재생성하려면 vLLM 컨테이너 내부에서
`bench/bench.sh`(또는 `python -m bench run`)를 사용하세요.
