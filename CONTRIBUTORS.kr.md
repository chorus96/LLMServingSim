# 기여자(Contributors)

LLMServingSim은 KAIST의 [CASYS](https://casys.kaist.ac.kr) 연구 그룹이 개발하고
유지 관리합니다. 이 프로젝트에 시간과 통찰, 코드를 기여해 주신 분들이 없었다면
지금의 모습이 될 수 없었을 것입니다. 이 페이지는 저희가 **감사**를 전하는
방법입니다.

## 핵심 팀 — CASYS, KAIST

- **Jaehong Cho** ([@JaehongCS20](https://github.com/JaehongCS20))
- **Hyunmin Choi** ([@hyuenmin-choi](https://github.com/hyuenmin-choi))
- **Guseul Heo**
- **Minsu Kim**
- **Jongse Park** — 지도 교수

## 커뮤니티 기여자

LLMServingSim을 모두에게 더 나은 것으로 만들기 위해 자발적으로 노력해 주신
CASYS 외부 기여자분들께 특히 감사드립니다. 🙏

- **[@horser1](https://github.com/horser1)**
  - 차원별 링크 설정 + collective 차원 동기화 ([#33](https://github.com/casys-kaist/LLMServingSim/pull/33))
  - Prefix-cache / radix-tree 수정 ([#35](https://github.com/casys-kaist/LLMServingSim/pull/35))
  - 인스턴스별 런타임 설정 오버라이드 ([#37](https://github.com/casys-kaist/LLMServingSim/pull/37))
  - 비-DP 다중 인스턴스 collective 스코핑 ([#39](https://github.com/casys-kaist/LLMServingSim/pull/39))
  - Run 격리 ASTRA-Sim 입력 경로 ([#43](https://github.com/casys-kaist/LLMServingSim/pull/43))
  - KV eviction/reload 회계 처리 ([#48](https://github.com/casys-kaist/LLMServingSim/pull/48))
- **[@Veilwalker](https://github.com/Veilwalker)**
  - 청크 프리필(chunked prefill)에서 prefix-cache 히트 중복 집계 방지 ([#49](https://github.com/casys-kaist/LLMServingSim/pull/49))
- **[@zsxh1990](https://github.com/zsxh1990)**
  - 인스턴스별 런타임 오버라이드 문서화 ([#38](https://github.com/casys-kaist/LLMServingSim/pull/38))
  - 임의 아키텍처를 위한 일반화된 PIM 지연 모델 ([#45](https://github.com/casys-kaist/LLMServingSim/pull/45))
- **[@shermanjlim](https://github.com/shermanjlim)**
  - `avail_size()` 과대추정 및 `storage_cache_evicted_req` 수정 ([#29](https://github.com/casys-kaist/LLMServingSim/pull/29))
- **[@gleb-kun](https://github.com/gleb-kun)**
  - 프로파일러 인자 파서의 누락된 반환값 수정 ([#22](https://github.com/casys-kaist/LLMServingSim/pull/22))

기여하셨는데 여기 등재되지 않았거나 항목을 갱신하고 싶으시면, pull request를
열거나 [연락](https://llmservingsim.ai/contact)해 주세요 — 모든 분의 작업이
인정받기를 바랍니다.

## 감사의 말(Acknowledgments)

`profiler/`의 기본 레이어별 프로파일 방법론은
[@waneon](https://github.com/waneon)에서 차용했습니다. LLMServingSim은
[ASTRA-Sim](https://github.com/astra-sim/astra-sim)과
[Chakra](https://github.com/mlcommons/chakra)를 기반으로 하며,
[vLLM](https://github.com/vllm-project/vllm)과
[SGLang](https://github.com/sgl-project/sglang)에서도 부분적으로 영감을 받았습니다.

---

기여에 관심이 있으신가요?
[기여자 가이드](https://llmservingsim.ai/docs/contributor/welcome)를 참고하세요.
