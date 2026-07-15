# scripts

공유 환경 / 빌드 진입점입니다. 모듈별 실행 스크립트(예: `profiler/profile.sh`,
`bench/bench.sh`, `workloads/examples/*.sh`)는 각 모듈과 함께 위치하며, 여기에는
설정 및 빌드 헬퍼만 있습니다.

## 파일

| 파일 | 용도 |
| --- | --- |
| `docker-vllm.sh`  | vLLM Docker 컨테이너 실행 (profiler + bench + workloads.generators). 저장소 루트를 `/workspace`로 마운트하고, 공식 `vllm/vllm-openai:v0.19.0` 이미지를 사용하며, 최초 실행 시 `datasets` + `matplotlib`를 미리 설치합니다. |
| `docker-sim.sh`   | 시뮬레이터 Docker 컨테이너 실행 (ASTRA-Sim + 시뮬레이터 Python 의존성). |
| `install-vllm.sh` | Docker가 없는 환경을 위해 `uv venv`를 통한 베어메탈 vLLM 설치. vLLM 0.19.0과 `datasets`, `matplotlib`를 포함합니다. |
| `compile.sh`      | ASTRA-Sim의 analytical 백엔드를 빌드하고 Chakra 트레이스 변환기를 설치합니다. |

## 일반적인 최초 설정

Docker 내부 (권장):

```bash
./scripts/docker-vllm.sh   # 프로파일링, 벤치마킹, 데이터셋 생성용
./scripts/docker-sim.sh    # 시뮬레이션용
./scripts/compile.sh       # 최초 1회 ASTRA-Sim + Chakra 빌드 (docker-sim 내부)
```

베어메탈 (vLLM 쪽만):

```bash
./scripts/install-vllm.sh
```

## 편집 시 참고

* `docker-vllm.sh`에는 자리 표시자 `HF_TOKEN="<your_token>"`이 들어 있습니다.
  실행 전에 실제 HuggingFace 토큰으로 설정하면 게이트된 설정(Llama 등)이 최초
  사용 시 자동으로 다운로드됩니다.
* `--gpus all`이 기본값입니다. 호스트를 다른 워크로드와 공유하려면
  `--gpus '"device=0,1"'`로 제한하세요.
