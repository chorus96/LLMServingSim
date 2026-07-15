---
sidebar_position: 7
title: 파생 프로파일 & 교체
---

# 파생 프로파일 & 교체

`profiler/perf/` 아래의 일부 프로파일은 측정된 것이 아니라 **파생된** 것입니다:
대상 모델에 대해 vLLM 프로파일러를 실행하는 대신, 같은 하드웨어에서 *다른* 모델의
측정된 프로파일을 해석적으로 스케일링하여 생성됩니다. 이는 아직 프로파일할 수 없는
모델(예: 손에 충분히 큰 GPU가 없는 70B 모델)을 위한 임시방편으로, 시뮬레이터가
그럼에도 아키텍처를 실행할 수 있게 합니다.

파생 프로파일은 구성상 근사적입니다 — 커널 실행 오버헤드, 텐서 코어 타일링, 대역폭
효과가 포착되지 않습니다 — 따라서 가능할 때마다 측정된 프로파일로 교체하세요.

## 파생 프로파일 식별

두 가지 마커:

1. 모델의 perf 폴더(`profiler/perf/<HW>/<MODEL>/README.md`)에 파생임을 밝히는
   `README.md`.
2. `meta.yaml`의 `derived:` 블록:

```yaml title="profiler/perf/RTXPRO6000/meta-llama/Llama-3.1-70B/bf16/meta.yaml"
derived:
  from: meta-llama/Llama-3.1-8B
  method: analytical per-layer FLOP/byte scaling (NOT measured)
  attention_prefill_factor: 2.0
  attention_decode_factor: 1.0
  dense_layer_factors: { o_proj: 4.0, qkv_proj: 3.333, act_fn: 2.0, ... }
```

측정된 프로파일에는 `derived:` 블록이 **없습니다**. 이것이 바로 교체가 성공했는지
확인하는 방법입니다.

## 경로 A — 실제 프로파일 측정 (권장)

이는 파생 번들을 제자리에서 덮어씁니다: 같은 `perf/<HW>/<MODEL>/<variant>/` 경로이므로,
이후 시뮬레이터나 설정 변경이 필요 없습니다.

### 1. 모델에 맞는 하드웨어 준비

프로파일러는 `hf_overrides`를 통해 랭크별 형상(`hidden_size`,
`num_attention_heads`, …)을 TP로 나누어 각 TP 차수를 **단일 GPU**에서
에뮬레이션하므로, 완전한 다중 GPU 박스가 필요 없습니다 — 하지만 랭크별 샤드와 그
activation이 하나의 GPU 메모리에 맞아야 합니다. `bf16`의 70B 모델의 경우, 실제로
실행할 TP 차수(예: `TP_DEGREES="2,4,8"`)를 프로파일하세요; 각 차수는 가중치가
`dummy`로 로드되어 부팅되므로 실제 체크포인트는 필요 없고, 샤딩된 형상에 충분한
VRAM만 필요합니다.

:::tip 모든 런타임 TP를 프로파일하세요
시뮬레이터는 인스턴스의 `tp_size`에 대해 `tp<N>/`을 조회합니다. 클러스터 설정이
`tp_size=4`를 실행하면, 프로파일에 `tp4/` 폴더가 **반드시** 있어야 하며, 그렇지
않으면 실행이 missing-variant 오류로 실패합니다. `TP_DEGREES`에 항상 `1`을
포함하세요; `tp_stable` 레이어는 거기서 한 번 프로파일되고 복제됩니다.
:::

### 2. vLLM 컨테이너 실행

```bash
./scripts/docker-vllm.sh
```

게이트된 설정이 최초 실행 시 다운로드되도록 `scripts/docker-vllm.sh`에 `HF_TOKEN`을
설정하세요. 전체 컨테이너 설명은 **[실행](./running)**을 참고하세요.

### 3. `profile.sh`를 모델로 향하게 하고 clean 실행을 강제

`profiler/profile.sh`를 편집:

```bash
MODEL="meta-llama/Llama-3.1-70B"   # 파생 프로파일과 같은 id
HARDWARE="RTXPRO6000"              # 같은 하드웨어 라벨 → 같은 perf/ 경로
TP_DEGREES="2,4,8"                 # 시뮬레이션할 모든 tp_size 커버
FORCE=1                            # 파생 CSV를 지우고 처음부터 재프로파일
```

`FORCE=1`이 중요합니다: 없으면 프로파일러가 재개하여 기존(파생) CSV 행을 미리
로드합니다. 그런 다음 실행:

```bash
./profiler/profile.sh
```

writer가 새 `dense.csv`, `per_sequence.csv`, `attention.csv`, `skew.csv`,
`skew_fit.csv`와 `derived:` 블록이 **없는** `meta.yaml`을 생성합니다. 이제 오래된
`README.md` 마커를 삭제하세요:

```bash
rm profiler/perf/RTXPRO6000/meta-llama/Llama-3.1-70B/README.md
```

### 4. 검증

```bash
# derived: 블록이 사라져야 함
grep -c "^derived:" profiler/perf/RTXPRO6000/meta-llama/Llama-3.1-70B/bf16/meta.yaml   # -> 0

# 관심 있던 시나리오를 재실행하고 파생 수치와 비교
python -m serving \
  --cluster-config 'configs/cluster/single_node_nelssa_70b_instance.json' \
  --dtype bfloat16 --enable-attn-offloading --sparse-attention-ratio 0.02 \
  --dataset 'workloads/example_trace.jsonl' --output 'outputs/nelssa_70b.csv'
```

파생 실행 대비 큰 TTFT/TPOT 변화는 예상되며 바로 그것이 요점입니다 — 측정된
프로파일은 FLOP 스케일링 모델이 포착할 수 없었던 커널 동작을 캡처합니다.

## 경로 B — 재파생 (여전히 GPU 없음)

아직 측정할 수 없지만 더 나은 근사를 원하면 — 다른 소스 모델, 하드웨어, 또는
variant — 파생 도구를 재실행하세요. 매번 `derived:` 출처를 재생성합니다:

```bash
python profiler/tools/derive_profile.py \
  --hardware RTXPRO6000 \
  --source meta-llama/Llama-3.1-8B \
  --target meta-llama/Llama-3.1-70B \
  --variant bf16 \
  --force
```

레이어별 스케일링이 정직하게 유지되도록 아키텍처가 대상에 가능한 한 가까운
`--source`(같은 `model_type`, 유사한 GQA 비율과 `head_dim`)를 선택하세요. 도구는
dense 레이어를 GEMM FLOP으로, `lm_head`/`sampler`를 `hidden×vocab` / `vocab`으로,
어텐션을 조각별로(프리필은 `num_attention_heads`, 디코드는 `num_key_value_heads ×
head_dim`) 스케일링합니다; `skew_fit` alpha는 스케일 불변이므로 그대로 복사됩니다.
레이어별 수는 스케일링되지 **않습니다** — 시뮬레이터가 런타임에 대상 설정의
`num_hidden_layers`를 곱합니다.

## 체크리스트

- [ ] `TP_DEGREES`가 클러스터 설정이 사용하는 모든 `tp_size`를 커버.
- [ ] `FORCE=1` 설정, 파생 행이 재개가 아니라 지워지도록.
- [ ] 실제 프로파일 실행 후 `meta.yaml`에 `derived:` 블록 없음.
- [ ] `README.md` 파생 마커 제거됨.
- [ ] 시뮬레이터 실행이 재현되고 수치가 타당해 보임.

## 참고

- **[실행](./running)** — 전체 프로파일러 실행 설명.
- **[출력 번들](./output-bundle)** — 시뮬레이터가 소비하는 CSV/`meta.yaml` 계약.
- **[NELSSA sparse attention](/docs/examples/disaggregated/nelssa-sparse-attention)**
  — 파생 Llama-70B 프로파일을 제공하는 연구.
