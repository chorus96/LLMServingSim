<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/static/img/llmservingsim_full_primary_dark_transparent.png">
    <img alt="LLMServingSim" src="docs/static/img/llmservingsim_full_primary_transparent.png" width="70%">
  </picture>
</p>

<h3 align="center">
이기종 및 분산형(Disaggregated) LLM 서빙 인프라를 위한 통합 시뮬레이터
</h3>

<p align="center">
| <a href="https://llmservingsim.ai"><b>웹사이트</b></a> | <a href="https://llmservingsim.ai/docs/getting-started/overview"><b>문서</b></a> | <a href="https://llmservingsim.ai/docs/contributor/welcome"><b>기여하기</b></a> | <a href="https://llmservingsim.ai/contact"><b>연락처</b></a> | <a href="https://llmservingsim.ai/changelog"><b>변경 이력</b></a> |
</p>

시뮬레이터를 시작하는 데 도움이 되도록 LLMServingSim 웹사이트를 구축했습니다. 문서, 기여 가이드, 팀 연락처 정보는 [llmservingsim.ai](https://llmservingsim.ai)를 방문하세요.

## 소개

LLMServingSim은 LLM 서빙 인프라를 위한 사이클 수준(cycle-level) 시뮬레이터입니다. vLLM의 continuous-batching 스케줄러를 반영한 Python 프런트엔드와 ASTRA-Sim C++ analytical 네트워크 백엔드를 결합하고, vLLM 기반 레이어별(layerwise) 프로파일러가 수집한 하드웨어별 지연 시간 데이터로 양쪽을 구동합니다. 그 결과 이기종 가속기, 분산형 메모리 계층(CPU / CXL / PIM), MoE 라우팅, 다중 인스턴스 병렬화(TP / PP / EP / DP)를 end-to-end로 연구할 수 있는 통합 환경이 됩니다.

## 시작하기

```bash
git clone --recurse-submodules https://github.com/casys-kaist/LLMServingSim.git
cd LLMServingSim
./scripts/docker-sim.sh           # 시뮬레이터 컨테이너 실행
./scripts/compile.sh              # ASTRA-Sim + Chakra 빌드
./serving/run.sh                  # 예제 시뮬레이션 실행
```

설치 세부 사항, 컨테이너 선택, 설정 레이아웃, CLI 플래그, 전체 예제 워크로드에
대해서는 [문서](https://llmservingsim.ai/docs/getting-started/overview)를 참고하세요.

## 논문

**ISPASS 2026**  
*LLMServingSim 2.0: A Unified Simulator for Heterogeneous and Disaggregated LLM Serving Infrastructure*  
Jaehong Cho<sup>\*</sup>, Hyunmin Choi<sup>\*</sup>, Guseul Heo, Jongse Park (KAIST) [[Paper]](https://doi.org/10.1109/ISPASS69572.2026.00012)  
<sup>\*</sup>공동 제1저자(Equal contribution)  
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18879965.svg)](https://doi.org/10.5281/zenodo.18879965)

**CAL 2025**  
*LLMServingSim2.0: A Unified Simulator for Heterogeneous Hardware and Serving Techniques in LLM Infrastructure*  
Jaehong Cho, Hyunmin Choi, Jongse Park (KAIST)  [[Paper]](https://doi.org/10.1109/LCA.2025.3628325)

**IISWC 2024**  
*LLMServingSim: A HW/SW Co-Simulation Infrastructure for LLM Inference Serving at Scale*  
Jaehong Cho, Minsu Kim, Hyunmin Choi, Guseul Heo, Jongse Park (KAIST)  [[Paper]](https://doi.org/10.1109/IISWC63097.2024.00012)  
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.12803583.svg)](https://doi.org/10.5281/zenodo.12803583)

## 인용

연구에 LLMServingSim을 사용하신다면 다음을 인용해 주세요:

```bibtex
@INPROCEEDINGS{11527300,
    author={Cho, Jaehong and Choi, Hyunmin and Heo, Guseul and Park, Jongse},
    booktitle={2026 IEEE International Symposium on Performance Analysis of Systems and Software (ISPASS)}, 
    title={{LLMServingSim 2.0: A Unified Simulator for Heterogeneous and Disaggregated LLM Serving Infrastructure}}, 
    year={2026},
    pages={1-14},
    doi={10.1109/ISPASS69572.2026.00012}
}

@ARTICLE{11224567,
    author={Cho, Jaehong and Choi, Hyunmin and Park, Jongse},
    journal={IEEE Computer Architecture Letters},
    title={{LLMServingSim2.0: A Unified Simulator for Heterogeneous Hardware and Serving
            Techniques in LLM Infrastructure}},
    year={2025},
    volume={24},
    number={02},
    pages={361-364},
    doi={10.1109/LCA.2025.3628325},
    ISSN={1556-6064},
    publisher={IEEE Computer Society},
    address={Los Alamitos, CA, USA},
    month=jul
}

@INPROCEEDINGS{10763697,
    author={Cho, Jaehong and Kim, Minsu and Choi, Hyunmin and Heo, Guseul and Park, Jongse},
    booktitle={2024 IEEE International Symposium on Workload Characterization (IISWC)},
    title={{LLMServingSim: A HW/SW Co-Simulation Infrastructure for LLM Inference Serving
            at Scale}},
    year={2024},
    pages={15-29},
    doi={10.1109/IISWC63097.2024.00012}
}
```
