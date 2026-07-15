---
sidebar_position: 1
title: 사전 요구 사항
---

# 사전 요구 사항

LLMServingSim은 Docker가 있는 Linux에서 실행됩니다. 시뮬레이터 측은 CPU에서
실행되지만, 프로파일러와 vLLM 벤치마크는 NVIDIA GPU가 필요합니다.

## 시스템

| | 시뮬레이터에 필요 | 프로파일러 / Bench에 필요 |
| --- | --- | --- |
| **OS** | Linux (Ubuntu 22.04+ 테스트됨) | Linux (Ubuntu 22.04+ 테스트됨) |
| **Docker** | ✓ | ✓ (또는 베어메탈 설치) |
| **NVIDIA GPU** |  | ✓ |
| **NVIDIA Container Toolkit** |  | ✓ (Docker로의 GPU passthrough용) |
| **CUDA driver** |  | 13.x 또는 호환 |
| **디스크** | ~3 GB | ~10 GB 추가 (vLLM 이미지 + HF 모델 캐시) |
| **RAM** | 16 GB | 32 GB+ 권장 |

미리 프로파일된 시뮬레이션(예: 번들된 RTXPRO6000 프로파일)만 실행할 계획이라면
GPU가 **필요하지 않습니다**.

## Docker 설치

Docker가 아직 없다면:

```bash
# Ubuntu, 공식 빠른 설치 스크립트
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

확인:

```bash
docker run --rm hello-world
```

## NVIDIA Container Toolkit 설치

GPU 컨테이너(프로파일러 / bench)에만 필요합니다. Ubuntu에서:

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

확인:

```bash
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```

GPU가 나열되어야 합니다. 그렇지 않으면
[문제 해결 → GPU 미감지](../troubleshooting#gpu-not-detected)를 참고하세요.

## Hugging Face 토큰 (선택)

일부 모델 설정(예: Llama 3.x, 게이트된 Qwen 변형)은 HF 인증 뒤에 있습니다.
프로파일러는 다음을 설정하면 이를 자동으로 fetch할 수 있습니다:

```bash
export HF_TOKEN="hf_xxxxxxxxxxxxxxxxxxxxxxxxxx"
```

새 모델을 **프로파일**할 계획일 때만 필요합니다. 미리 프로파일된 시뮬레이션 실행에는
HF 토큰이 필요 없습니다.

[huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)에서 토큰을
받으세요.

## 다음

이제 설치할 준비가 되었습니다. 모두에게 필요한 주요 설치 경로인
**[시뮬레이터 설정](./simulator)**으로 계속하세요.
