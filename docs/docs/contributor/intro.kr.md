---
sidebar_position: 2
title: 온보딩
---

# 온보딩

이 페이지는 새 클론에서 동작하는 시뮬레이터 실행까지 개발 환경을 안내합니다. 목표:
끝날 무렵 `serving/`의 Python 파일을 편집하고, 시뮬레이션을 재실행하고, 변경이 출력
CSV에 반영되는 것을 볼 수 있어야 합니다.

코드를 읽기만 할 계획이라면(실행 안 함), 대신 **[코드베이스 둘러보기](./codebase-tour)**로
건너뛰세요.

## 사전 요구 사항

- Linux(Ubuntu 22.04+ 테스트됨). macOS는 편집에는 동작하지만 프로파일러 / bench 실행에는
  아님(그것들은 NVIDIA GPU 필요).
- Docker(가장 간단한 경로) 또는 Docker를 쓸 수 없으면 베어메탈 vLLM 설치기.
- 시뮬레이터 컨테이너용 ~5 GB 여유 디스크, 프로파일이나 bench도 한다면 ~10 GB 추가.
- GitHub 계정(최종 PR용).

시뮬레이터 실행만을 위해서는 GPU가 **필요 없습니다**. 번들된 RTXPRO6000 / H100 프로파일
번들로 하드웨어 없이 시뮬레이션할 수 있습니다.

## 1. 서브모듈과 함께 클론

ASTRA-Sim은 git 서브모듈로 존재합니다. 항상 `--recurse-submodules`로 클론하세요:

```bash
git clone --recurse-submodules https://github.com/casys-kaist/LLMServingSim.git
cd LLMServingSim
```

서브모듈 없이 이미 클론했으면:

```bash
git submodule update --init --recursive
```

## 2. 컨테이너 선택

두 컨테이너, 역할당 하나:

| 컨테이너 | 이미지 | 언제 필요 |
| --- | --- | --- |
| `scripts/docker-sim.sh` | `astrasim/tutorial-micro2024` + Python 의존성 | 시뮬레이터 실행. **항상.** |
| `scripts/docker-vllm.sh` | `vllm/vllm-openai:v0.19.0` | 새 하드웨어 프로파일, bench 실행, ShareGPT에서 워크로드 생성. **그것들을 건드릴 때만.** |

대부분의 기여자 작업(스케줄러, 메모리 모델, 트레이스 생성기, 설정)에는 sim 컨테이너면
충분합니다:

```bash
./scripts/docker-sim.sh
```

이는 모든 Python 의존성이 설치된 `/app/LLMServingSim`의 셸로 들어갑니다. 저장소 루트가
bind-mount되므로, 호스트의 편집이 내부에서 즉시 보입니다.

## 3. ASTRA-Sim과 Chakra 빌드

sim 컨테이너 내에서, 최초 실행 시:

```bash
./scripts/compile.sh
```

이는 ASTRA-Sim의 analytical 백엔드(시뮬레이터가 사용)를 컴파일하고 Chakra 트레이스
변환기를 설치합니다. 처음에는 몇 분, 증분 재빌드는 ~30초. `astra-sim/` C++ 소스를 건드릴
때마다 재실행하세요.

컴파일이 누락된 의존성으로 실패하면, 가장 흔한 원인은 서브모듈이 체크아웃되지 않은
것입니다. 호스트에서 `git submodule update --init --recursive`를 재실행하고 다시
시도하세요.

## 4. Smoke 실행

가장 빠른 "모든 것이 동작하나?" 확인은 번들된 단일 인스턴스 트레이스입니다:

```bash
python -m serving \
    --cluster-config configs/cluster/single_node_single_instance.json \
    --dataset workloads/example_trace.jsonl \
    --output outputs/onboarding_smoke.csv \
    --num-reqs 10
```

보여야 할 것:

- 몇 초의 throughput 로그 라인(`step=N batch=K prompt_t=… decode_t=…`).
- 끝에 총계를 가진 요약 라인(`Finished N requests`).
- 요청당 한 행을 담은 `outputs/onboarding_smoke.csv`.

그것을 얻었으면, 시뮬레이터가 동작합니다. 오류를 얻었으면
**[문제 해결](/docs/getting-started/troubleshooting)**을 참고하세요.

## 5. 실제 변경하기

이제 실제로 무언가를 편집할 시간입니다. 안전한 첫 편집: throughput 업데이트를 더 자주
볼 수 있도록 기본 로그 간격을 올리기.

`serving/__main__.py`를 열고 `--log-interval` 인자(기본 `1.0`)를 찾으세요. 기본값을
`0.5`로 변경하고, 저장하고, 단계 4의 smoke 명령을 재실행하세요. throughput 로그 라인이
두 배로 보여야 합니다.

가지고 놀기가 끝나면 변경을 되돌리세요(`git checkout serving/__main__.py`).

## 6. 다음 페이지 읽기

이제 설정되었습니다. PR을 열기 전에, 다음을 훑어보세요:

- **[코드베이스 둘러보기](./codebase-tour)**: 각 종류의 변경이 어디에 있는지.
- **[코딩 규약](./conventions)**: 코드베이스를 읽기 좋게 유지하는 작은 규칙 집합.
- **[변경 사항 검증](./validating-changes)**: 변경이 아무것도 깨뜨리지 않았는지 아는
  방법(단위 테스트 스위트가 없으므로 이것이 중요).
- **[PR 워크플로우](./pr-workflow)**: 브랜치, 커밋 메시지 스타일, PR 템플릿.

## 흔한 설정 함정

1. **`--recurse-submodules` 잊음** → ASTRA-Sim이 없고, `compile.sh`가 즉시 실패. `git
   submodule update --init --recursive`를 재실행하세요.
2. **작업에 잘못된 컨테이너** → 프로파일러 / bench 스크립트가 누락된 CUDA나 vLLM에 대해
   불평. `scripts/docker-vllm.sh`로 전환하세요.
3. **편집이 컨테이너 내에서 안 보임** → 편집이 클론된 저장소 디렉터리 아래에
   착지했는지 확인하세요(컨테이너가 전체 홈 디렉터리가 아니라 저장소 루트를 마운트).
4. **Python 버전 불일치** → 두 컨테이너 모두 올바른 Python을 제공; 자신의 것을 설치하려
   하지 마세요. 베어메탈로 실행해야 하면 `scripts/install-vllm.sh`가 vLLM 측을
   처리합니다.
5. **`docker-sim.sh`가 컨테이너가 존재한다고 함** → 재실행 전에 재연결(`docker exec -it
   servingsim_docker bash`)하거나 제거(`docker rm -f servingsim_docker`)하세요.

## 도움을 요청할 곳

- **GitHub Discussions**:
  [casys-kaist/LLMServingSim/discussions](https://github.com/casys-kaist/LLMServingSim/discussions).
  "어떻게…" 질문의 첫 정거장.
- **GitHub Issues**: 설정 blocker는 제목에 `[contributor]`를 넣어
  [casys-kaist/LLMServingSim/issues](https://github.com/casys-kaist/LLMServingSim/issues)에
  등록하세요.
- **주요 기여자에게 이메일**:
  [jhcho@casys.kaist.ac.kr](mailto:jhcho@casys.kaist.ac.kr?cc=hmchoi@casys.kaist.ac.kr)과
  [hmchoi@casys.kaist.ac.kr](mailto:hmchoi@casys.kaist.ac.kr?cc=jhcho@casys.kaist.ac.kr)
  (가능하면 항상 둘 다 CC).
