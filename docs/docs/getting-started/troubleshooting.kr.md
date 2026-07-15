---
sidebar_position: 4
title: 문제 해결
---

# 문제 해결

설치 및 첫 실행 중 흔한 오류와 가장 빠른 해결책입니다.

여기에 문제가 없으면
[github.com/casys-kaist/LLMServingSim/issues](https://github.com/casys-kaist/LLMServingSim/issues)에
전체 명령, 오류 출력, OS / Docker / GPU 버전과 함께 버그를 신고해 주세요.

## 서브모듈이 없음

**증상:** `astra-sim/extern/graph_frontend/chakra/` 또는 `astra-sim/build/` 아래의
누락된 파일에 대한 오류로 빌드가 실패합니다.

**원인:** `--recurse-submodules` 없이 클론했습니다.

**해결:**

```bash
git submodule update --init --recursive
```

그런 다음 `./scripts/compile.sh`를 다시 실행하세요.

## `docker: permission denied`

**증상:**

```text
docker: Got permission denied while trying to connect to the
Docker daemon socket
```

**원인:** 사용자가 `docker` 그룹에 없습니다.

**해결:**

```bash
sudo usermod -aG docker $USER
newgrp docker
# 또는 로그아웃 후 다시 로그인
```

## GPU 미감지

**증상:** vLLM 컨테이너 안에서 `nvidia-smi`가 `command not found` 또는 `no devices
found`라고 합니다.

**원인:** NVIDIA Container Toolkit이 설치되지 않았거나 Docker가 이를 사용하도록
설정되지 않았습니다.

**해결:** 툴킷을 설치 / 재설정하고(
[사전 요구 사항](./installation/prerequisites#install-nvidia-container-toolkit) 참고)
Docker를 재시작하세요:

```bash
sudo systemctl restart docker
```

그런 다음 확인:

```bash
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```

호스트의 `nvidia-smi`는 동작하지만 컨테이너의 것은 동작하지 않으면 툴킷이
문제입니다. 호스트의 `nvidia-smi`도 실패하면 먼저 NVIDIA 드라이버를 설치하세요.

## Hugging Face: 게이트된 모델 / 401 / 403

**증상:** Llama 3.x 또는 게이트된 Qwen 변형을 프로파일할 때:

```text
huggingface_hub.utils._errors.GatedRepoError: Access to model
meta-llama/Llama-3.1-8B is restricted...
```

**해결:**

1. 모델 페이지에서 라이선스에 동의(일회성, huggingface.co에서).
2. vLLM 컨테이너를 실행하기 **전에** 셸에서 `HF_TOKEN`을 설정:

   ```bash
   export HF_TOKEN="hf_xxxxxxxxxxxxxxxxxxxxxxxxxx"
   ./scripts/docker-vllm.sh
   ```

토큰은 컨테이너로 자동 전달됩니다. 컨테이너 안에서 `echo $HF_TOKEN`으로 확인하세요.

## ASTRA-Sim 빌드 실패

**증상:** `./scripts/compile.sh`가 종종 CMake나 컴파일러 메시지와 함께 도중에
오류로 종료됩니다.

**흔한 원인 & 해결:**

- **컨테이너 안에 빌드 의존성 누락.** 공식 `astrasim/tutorial-micro2024`
  이미지에는 기본적으로 포함되어 있습니다. 이미지를 커스터마이즈했다면 `cmake`,
  `g++`, `protobuf-compiler`, `libprotobuf-dev`, `libboost-dev`가 설치되어 있는지
  확인하세요.
- **오래된 빌드 상태.** 빌드 디렉터리를 지우고 재시도:

  ```bash
  rm -rf astra-sim/build/astra_analytical/build/
  ./scripts/compile.sh
  ```
- **컨테이너 밖에서 실행.** `compile.sh`는 호스트가 아니라 시뮬레이터 컨테이너
  안에서 실행하도록 되어 있습니다. 먼저 `./scripts/docker-sim.sh`를 사용하세요.

## 컨테이너 이름이 이미 사용 중

**증상:**

```text
docker: Error response from daemon: Conflict. The container name
"/servingsim_docker" is already in use by container "abc123..."
```

**원인:** 이전 실행이 컨테이너를 남겨두었습니다.

**해결:** 재연결하거나 제거 후 재생성합니다.

```bash
# 기존에 재연결
docker start -ai servingsim_docker

# 또는 지우고 재생성
docker rm -f servingsim_docker
./scripts/docker-sim.sh
```

`vllm_docker`도 같은 방식입니다.

## 프로파일 데이터 누락

**증상:** 프로파일 데이터가 없는 하드웨어 / 모델 조합으로 시뮬레이터를 실행:

```text
FileNotFoundError: ../profiler/perf/<hardware>/<model>/<variant>/tp1/dense.csv
```

**원인:** `(hardware, model, dtype, kv_cache_dtype)` 튜플에 프로파일된 CSV 번들이
없습니다.

**해결:** 다음 중 하나

- 이미 프로파일된 하드웨어 / 모델 조합을 선택
  ([시뮬레이터 → 출력 읽기](/docs/simulator/reading-output) 표 참고), 또는
- **[프로파일러](/docs/profiler/overview)**를 실행하여 누락된 번들을 직접 생성.

## 시작 시 `--max-num-batched-tokens` 경고

**증상:**

```text
WARNING: runtime --max-num-batched-tokens (4096) exceeds profiled
sweep bound (2048). Lookups will extrapolate.
```

**원인:** 프로파일러가 스윕한 것보다 큰 토큰 예산으로 시뮬레이터를 실행하고
있습니다. 지연 조회가 측정 범위를 넘어 선형으로 외삽됩니다.

**해결:**

- 최상의 정확도를 위해, 더 높은 `--max-num-batched-tokens`로 재프로파일
  (`MAX_NUM_BATCHED_TOKENS=4096 ./profiler/profile.sh`).
- 또는 프로파일된 경계에 머물기. 외삽은 작은 초과에는 대체로 괜찮지만, 큰 초과는
  drift할 수 있습니다.

## 큰 워크로드에서 시뮬레이터가 멈추거나 매우 느림

**증상:** 시뮬레이션이 실행되지만 특히 MoE + EP나 큰 prefix cache에서 예상보다
훨씬 오래 걸립니다.

**흔한 원인 & 해결:**

- **Block-copy 비활성화.** MoE의 경우 `--enable-block-copy`를 켜 두세요(기본값).
  이는 레이어별로 라우팅을 재계산하는 대신 하나의 transformer 블록 트레이스를 모든
  레이어에 걸쳐 재생합니다. `--expert-routing-policy BALANCED`(기본, 결정적)에
  안전; `RR`/`RAND`는 레이어별 분산을 평균화합니다.
- **Verbose 로깅.** `--log-level DEBUG`는 많이 씁니다. `--log-level INFO`나
  `WARNING`으로 낮추세요.
- **`--log-interval`이 너무 작음.** `0.1`로 설정하면 로거가 100 ms마다 실행됩니다;
  `1.0`(기본) 이상으로 올리세요.

## vLLM 컨테이너 안에서 메모리 부족

**증상:** 어텐션 스윕 도중 프로파일러가 CUDA OOM으로 크래시합니다.

**해결:** `profiler/profile.sh`에서 `MAX_NUM_BATCHED_TOKENS`를 낮추거나, 환경
변수로 무거운 카테고리를 건너뛰세요([프로파일러 → 실행](/docs/profiler/running)
참고).

## 여전히 막혀 있나요?

- **GitHub Issues:** [casys-kaist/LLMServingSim/issues](https://github.com/casys-kaist/LLMServingSim/issues)
- **Discussions:** [casys-kaist/LLMServingSim/discussions](https://github.com/casys-kaist/LLMServingSim/discussions)

버그를 신고할 때 다음을 포함해 주세요:

1. 실행한 정확한 명령
2. 전체 오류 출력
3. OS, Docker 버전, NVIDIA 드라이버, GPU 모델
4. 시뮬레이터 컨테이너 안인지 vLLM 컨테이너 안인지(또는 베어메탈인지)
