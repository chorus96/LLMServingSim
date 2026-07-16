---
title: Artifact 평가
sidebar_position: 7
description: 발표된 LLMServingSim 논문의 figure와 결과를 재현
---

# Artifact 평가

Artifact를 제공하는 각 LLMServingSim 논문은 artifact-evaluation 위원회에 제출된 상태로
고정된 자체 브랜치에 있습니다. 이 페이지는 발표된 figure를 end-to-end로 재현하려는
리뷰어와 독자를 위한 진입점입니다.

> **주의:** artifact 브랜치는 재현성을 위해 고정되어 있습니다. 그것들에 대해 PR을 열지
> 마세요; 새 개발은 `main`으로 갑니다. **[기여자용 → PR
> 워크플로우](/docs/contributor/pr-workflow)**를 참고하세요.

## 사용 가능한 artifact

| 논문 | 발표처 | 브랜치 | 재현 |
| --- | --- | --- | --- |
| **LLMServingSim 2.0** | ISPASS 2026 | [`ispass26-artifact`](https://github.com/casys-kaist/LLMServingSim/tree/ispass26-artifact) | Figure 5–10 |
| **LLMServingSim** | IISWC 2024 | (릴리스된 artifact, [Zenodo DOI](https://doi.org/10.5281/zenodo.12803583) 참고) | 원본 논문 figure |

CAL 2025 항목은 ISPASS 2026 코드베이스를 공유하며 자체 artifact 브랜치가 없습니다.

## ISPASS 2026 — `ispass26-artifact`

*Cho, Choi, Heo, Park. "LLMServingSim 2.0: A Unified Simulator for Heterogeneous and
Disaggregated LLM Serving Infrastructure", ISPASS 2026.
[Zenodo DOI](https://doi.org/10.5281/zenodo.18879965).*

이 브랜치는 논문의 **Figure 5부터 10까지**와 `evaluation/` 아래의 보조 throughput /
power / memory / latency 파서를 재현합니다.

> Artifact는 v1.1.0 디렉터리 재구성과 vLLM 기반 프로파일러 재작성보다 앞서므로,
> `ispass26-artifact`에서는 이 사이트의 나머지가 문서화하는 `serving/` / `configs/` /
> `workloads/` / `outputs/` 경로 대신 이전 레이아웃(`cluster_config/`, `dataset/`,
> `output/`, `inference_serving/`, `main.py`)을 보게 됩니다. Artifact 안에 있는 동안은 이
> 사이트의 Getting Started가 아니라 브랜치 자체의 README를 따르세요.

### 1. Artifact 브랜치로 전환

```bash
git clone --recurse-submodules https://github.com/casys-kaist/LLMServingSim.git
cd LLMServingSim
git checkout ispass26-artifact
```

이미 클론했으면, 고정된 ASTRA-Sim 서브모듈을 가져오기 위해 `git checkout
ispass26-artifact`와 `git submodule update --init --recursive`만 하세요.

### 2. 환경 설정

Artifact는 (`main`의 두 컨테이너 분리 대신) 자체 Docker 실행기와 빌드 스크립트를
제공합니다:

```bash
./docker.sh        # artifact의 시뮬레이터 컨테이너 실행
./compile.sh       # 컨테이너 내에서 ASTRA-Sim + Chakra 빌드
```

`docker.sh`가 저장소를 `/app/LLMServingSim`에 마운트합니다. 이후 모든 명령을 컨테이너 내
그 작업 디렉터리에서 실행하세요.

### 3. 단일 figure 재현

각 figure는 `evaluation/` 아래 자체 드라이버 스크립트를 가집니다:

```bash
cd evaluation

bash figure_5.sh        # 하드웨어 커버리지 (A6000, H100)
bash figure_6.sh        # 다중 인스턴스 + P/D 분리
bash figure_7.sh        # MoE expert 병렬화 + offloading
bash figure_8.sh        # CPU / CXL pool에 걸친 prefix caching
bash figure_9.sh        # CXL 메모리 확장
bash figure_10.sh       # 전력 및 에너지 모델링
```

각 스크립트는 중간 로그를 `evaluation/figure_X/logs/`에, 파싱된 수치를
`evaluation/figure_X/parsed/`에, 최종 PDF를 스크립트 옆에 씁니다.

### 4. 모두 재현

```bash
cd evaluation
bash run_all.sh
```

이는 여섯 개 `figure_*.sh` 스크립트를 순서대로 모두 실행하는 것과 같습니다. 단일
워크스테이션에서 몇 시간이 걸릴 것으로 예상하세요; 각 figure가 많은 시뮬레이터 호출을
실행합니다.

### 5. 보존된 스냅샷과 비교

고정된 참조 출력은 `evaluation/artifacts/` 아래에 있습니다. 생성한 파싱 출력을 그
스냅샷과 비교하려면:

```bash
# 모든 figure 비교
bash compare.sh

# 하나의 figure 비교
bash compare.sh 5

# 부분집합 비교
bash compare.sh 5 7 9
```

시각적 확인을 위해, 재생성된 `figure_X.pdf`를 각 폴더의 커밋된
`figure_X_ref.pdf`(다중 패널 figure는 `figure_Xa_ref.pdf`)와 비교하세요.

### Figure별 세부 사항

각 `evaluation/figure_X/` 폴더는 figure의 목표, 축 정의, 참조 입력, 예상 TSV 파일, PDF
명명 규약을 가진 자체 `README.md`를 가집니다. Figure 재현이 실패하거나 수치가 비교
허용치 밖으로 drift하면 거기서 시작하세요.

포괄 참조는
[`evaluation/README.md`](https://github.com/casys-kaist/LLMServingSim/blob/ispass26-artifact/evaluation/README.md)이며,
모든 figure에 걸쳐 사용되는 파서, 폰트, 폴더 레이아웃을 나열합니다.

## 재현이 실패할 때

몇 가지 흔한 경우:

1. **`compile.sh`가 서브모듈에서 오류**: 호스트에서 `git submodule update --init
   --recursive`를 재실행하고 다시 시도하세요. 서브모듈 pin은 artifact의 일부입니다.
2. **`figure_X.sh`가 실행되지만 파싱 출력이 일치하지 않음**: artifact가 인증된 허용
   대역에 대해 해당 `evaluation/figure_X/README.md`를 확인하세요; 정확한 와트나 지연
   값의 작은 drift는 정성적 추세가 참조 PDF와 일치하는 한 예상됩니다.
3. **특정 시뮬레이터 명령이 브랜치에서 실패하지만 `main`에서는 동작**: 그것은
   예상됩니다. Artifact는 논문 제출 상태에 고정되어 있습니다; 이후 `main`에 도착한 버그
   수정과 새 기능은 back-port되지 않습니다.
4. **Artifact를 확장해야 함**(예: Figure 5에 새 GPU 추가): 대신 `main`에서 작업하고 새
   결과를 별도로 인용하는 것을 권장합니다. Artifact 브랜치는 논문에 대해 재현 가능한
   상태로 유지되어야 합니다.

## Artifact 저자에게 연락

Artifact 관련 질문(재현 실패, 환경 설정, 누락된 참조 출력 요청)은 주요 기여자에게
이메일을 보내세요:

- [jhcho@casys.kaist.ac.kr](mailto:jhcho@casys.kaist.ac.kr?cc=hmchoi@casys.kaist.ac.kr)
- [hmchoi@casys.kaist.ac.kr](mailto:hmchoi@casys.kaist.ac.kr?cc=jhcho@casys.kaist.ac.kr)

가능하면 항상 둘 다 CC하세요. 전체 채널 목록은 [연락처 페이지](/contact)를 참고하세요.
