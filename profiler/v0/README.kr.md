# llm_profile v0 (Pytorch profiler)

LLM 레이어 지연 시간, 어텐션 지연 시간, GPU/시스템 수준 전력 소비를 측정하기 위한
PyTorch 기반 프로파일링 도구입니다. 출력은 LLMServingSim에서 성능 및 전력
모델로 사용됩니다.

LLMServingSim에서 사용할 새 모델이나 하드웨어 타깃을 프로파일하려면 아래 단계를
따르세요. 최상위 README의 [새 모델 & 하드웨어 추가](../README.md#adding-a-new-model--hardware)
섹션도 참고하세요.

## 개요

`llm_profile`은 Hugging Face에서 모델을 로드하고 주요 레이어에 PyTorch
프로파일러 훅을 삽입하여 GPU에서의 실행 시간을 측정합니다. dense 및 MoE
아키텍처를 지원하며, 레이어별 지연 시간 CSV와 scikit-learn 기반 어텐션 지연
예측기를 생성합니다. GPU 및 시스템 수준 전력 소비는 `nvidia-smi`와
`ipmitool`로 측정하며, 결과는 LLMServingSim의 전력 모델에 입력됩니다.

## 사용법

### 1. 환경

제공된 Docker 컨테이너 또는 네이티브 PyTorch + CUDA 환경 내부에서 실행:

```bash
./docker.sh
```

접근 승인이 필요한 모델(예: LLaMA)의 경우, `docker.sh`에 설명된 대로 Hugging
Face 토큰을 제공하세요.

### 2. 레이어 및 어텐션 프로파일

```bash
./profile_layers.sh    # 비-어텐션 레이어의 연산 지연 시간 측정
./profile_attn.sh      # 배치 크기와 시퀀스 길이에 걸친 어텐션 지연 시간 측정
```

프로파일링 시간과 메모리 사용량을 줄이려면, 각 프로파일링 스크립트에서
`--num-layer`로 레이어 수를 줄이세요.

### 3. 전력 프로파일 (선택)

전력 측정을 위해, `nvidia-smi`로 GPU 전력 소비를, `ipmitool`로 시스템 수준
전력을 측정하는 예제 스크립트를 `profiler/power/` 아래에 제공합니다:

```bash
./profiler/power/profile_gpu_power.sh      # nvidia-smi를 통한 GPU 전력
./profiler/power/profile_server_power.sh   # ipmitool을 통한 시스템 수준 전력
```

전력 프로파일링 결과는 전력 설정이 포함된 클러스터 설정(예:
`cluster_config/single_node_power_instance.json`)이 제공될 때
LLMServingSim의 전력 모델에서 사용됩니다.

### 4. 어텐션 예측기 빌드

```bash
./build_predictor.sh
```

프로파일된 어텐션 데이터로 scikit-learn 모델을 학습하여 시뮬레이션 중
실시간 지연 예측(`--enable-attn-prediction`)을 지원합니다. 예측기가 커버하는
추론 공간은 `--max-batch`와 `--max-len`으로 제어할 수 있습니다.

## 출력 구조

결과는 다음에 기록됩니다:

```
perf_models/{hardware}/{model}/tp{tp_size}/
  layers.csv                              # 레이어별 연산 지연 시간
  attention.csv                           # (batch_size, seq_len)별 어텐션 지연 시간
  predictions/
    attn_decode_predictions.csv           # 디코드 어텐션에 대한 예측기 출력
    attn_prefill_predictions.csv          # 프리필 어텐션에 대한 예측기 출력
```

이 파일들은 런타임에 LLMServingSim이 자동으로 로드합니다.

## 지원 모델

모델별 프로파일링 코드는 `models/`에 있습니다:

- `llama.py` — Llama 아키텍처 (Llama-3.1-8B, Llama-3.1-70B)
- `mixtral.py` — Mixtral-8x7B (MoE)
- `phimoe.py` — Phi-mini-MoE-instruct (MoE)

## 새 모델 또는 하드웨어 추가

1. 기존 예제를 따라 `models/`에 모델 프로파일링 스크립트를 추가합니다.
2. 프로파일링 셸 스크립트에서 대상 하드웨어 이름과 모델 식별자를 설정합니다.
3. 위의 프로파일링 및 예측기 빌드 단계를 실행합니다.
4. 새 하드웨어 이름을 참조하는 `cluster_config` 항목을 생성합니다.
