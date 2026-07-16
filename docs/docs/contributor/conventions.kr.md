---
sidebar_position: 4
title: 코딩 규약
---

# 코딩 규약

짧은 체크리스트. PR을 열기 전에 훑어보세요. 이들 중 어느 것도 임의적이지 않습니다; 각각
프로젝트를 최소 한 번은 물었습니다.

## Python 스타일

- **4칸 들여쓰기, 함수/변수는 snake_case, 클래스는 PascalCase.** 편집 중인 파일의 주변
  코드와 일치시키세요.
- **강제 포매터 없음.** 파일을 재작성하는 것이 아니라면 전체 파일에 black / ruff format을
  실행하지 마세요. 스타일 노이즈가 실제 diff를 숨깁니다.
- **임포트**: 최소하고 일관되게 유지. `serving/` 모듈은 상대 임포트(`from .scheduler
  import …`)를 사용.
- 코드, 주석, 로그 메시지, docstring에서 **영어만**. 한국어 / 다른 언어 식별자와 주석은
  리뷰에서 플래그됩니다.
- **Docstring**: 선택. 작성한다면, 함수가 *무엇을 하는지*가 아니라 *왜 존재하는지*를
  설명하는 한 줄로 만드세요. 시그니처가 이미 무엇을 하는지 말합니다.
- **최상위 print 없음.** `serving/core/logger.py`(대부분의 파일에 `logger`로 이미 임포트됨)를
  사용하세요:
  ```python
  logger.info(...)
  logger.warning(...)
  logger.success(...)   # Rich 스타일 녹색 체크
  ```

## CLI 플래그 규약

- **CLI 플래그는 하이픈 사용**: `--cluster-config`, `--max-num-seqs`,
  `--enable-prefix-caching`.
- **내부 Python은 언더스코어 사용**: `cluster_config`, `max_num_seqs`,
  `enable_prefix_caching`.
- **Boolean 플래그는 `BooleanOptionalAction`을 사용**하여 `--enable-X`와 `--no-enable-X`
  둘 다 동작하도록:
  ```python
  parser.add_argument('--enable-prefix-caching',
                      action=argparse.BooleanOptionalAction,
                      default=True)
  ```
- 해당되는 경우 **vLLM 이름과 일치**(`--max-num-batched-tokens`, `--block-size`,
  `--kv-cache-dtype`). vLLM에서 온 사용자가 다시 배울 필요가 없어야 합니다.

## 파일 및 설정 명명

- **JSON 설정 파일 이름**: 서술적 snake_case(`single_node_pim_instance.json`, `singleNodePimInstance.json`
  아님).
- **하나의 설정 = 하나의 시나리오.** 무관한 예제 간에 같은 클러스터 JSON을 재사용하지
  마세요; 복사하세요.
- **머신별 경로를 커밋하지 마세요.** 코드와 설정의 모든 경로는 저장소 루트 기준
  상대여야 합니다.

## 결코 하지 말 것

이들 각각은 실제 사건이나 강한 프로젝트 선호에 대응합니다:

1. **`Request` 속성에 `getattr(request, 'attr', default)` 폴백을 추가하지 마세요.** 모든
   속성을 `Request.__init__`에서 초기화하고 직접 접근하세요. 폴백이 초기화 버그를
   숨깁니다.

2. **`hidden_size == num_heads * head_dim`을 가정하지 마세요.** 일부 모델(Qwen3)이 이를
   위반합니다. 항상:
   ```python
   head_dim = config.get('head_dim', n_embd // n_head)
   q_dim   = n_head * head_dim         # n_embd 아님
   kv_dim  = kv_head * head_dim        # n_embd // group 아님
   ```

3. **레이어 이름을 만들지 마세요.** 시뮬레이터가 생성하는 모든 이름은 아키텍처 YAML의
   catalog에도 나타나야 합니다. 정식 집합: `qkv_proj`, `o_proj`, `gate_up_proj`,
   `act_fn`, `down_proj`, `rotary_emb`, `qk_norm`, `attention`, `layernorm`,
   `final_layernorm`, `embedding`, `lm_head`, `sampler`, `moe`.

4. 변경이 시뮬레이터 통합(Chakra 변환기, `Workload.cc`, 입력 설정)을 대상으로 하지 않는
   한 **`astra-sim/`를 편집하지 마세요.** 대부분의 기여는 이 디렉터리를 결코 건드리지
   않습니다.

5. **`astra-sim/inputs/*.json`을 수동으로 편집하지 마세요.** 그 파일들은 매 실행마다
   `config_builder.py`가 재생성합니다; 편집이 조용히 덮어쓰입니다.

6. **큰 생성 파일을 커밋하지 마세요.** 트레이스 파일, 로컬 실행의 `outputs/*.csv`, `.et`
   protobuf, gitignore 패턴을 초과하는 프로파일러 번들 CSV는 로컬에 유지해야 합니다.
   gitignore가 설정되어 있습니다; 그냥 `git add -A`를 하지 마세요.

7. **pre-commit 훅을 우회하기 위해 `--no-verify`를 사용하지 마세요.** 훅이 실패하면,
   기저 문제를 고치세요.

8. **일어날 수 없는 경우에 대한 오류 처리를 추가하지 마세요.** 내부 불변식을 신뢰하세요;
   경계(CLI 인자, JSON 설정 로드, 데이터셋 파싱)에서만 검증하세요. `scheduler.py` 내부의
   방어적 프로그래밍은 파일을 읽을 수 없게 만듭니다.

9. **당면 작업을 넘어서는 기능을 추가하지 마세요.** 버그 수정에 주변 정리가 필요 없습니다.
   비슷한 세 줄이 성급한 추상화보다 낫습니다.

10. **코드가 무엇을 하는지 설명하는 주석을 추가하지 마세요.** 식별자 이름이 이미 그것을
    합니다. 주석은 명백하지 않은 무언가가 *왜* 그런지(숨겨진 불변식, 버그 우회, 논문
    인용)를 위해 예약됩니다.

## 레이어 이름 및 단위 주의사항

이 둘이 새 기여자를 가장 자주 걸려 넘어지게 합니다:

- **프로파일러 CSV는 마이크로초를 저장(`time_us` 열).** 시뮬레이터가 로드 시 1000을
  곱하고 나노초로 반올림합니다. 두 번 나누지 마세요.
- **ASTRA-Sim의 통신 크기는 (NPU별이 아니라) *전체* 바이트입니다.** ASTRA-Sim이 ring
  크기로 내부적으로 나눕니다. NPU별 크기를 전달하면, 모든 collective가 N배 너무
  작아집니다.

## 트레이스 형식 불변식

`trace_generator.py`나 `graph_generator.py`를 건드린다면:

- **첫** 레이어의 `input_loc`과 **마지막** 레이어의 `output_loc`은 `REMOTE:{node_id}`여야
  합니다. Chakra 변환기가 첫 것에서 `MEM_LOAD`를, 마지막 것에서 `MEM_STORE`를 생성합니다;
  둘 중 하나라도 로컬 메모리 설정 없이 `LOCAL`이면, ASTRA-Sim이 크래시합니다.
- sampler의 `output_loc`이 `MEM_STORE`에 입력되는 것입니다. `lm_head`에 두지 마세요.

## 커밋 및 PR 스타일

짧은 버전(전체 프로세스는 **[PR 워크플로우](./pr-workflow)**에 있음):

- **커밋 메시지**: 짧은 명령형 한 줄.
  - 좋음: `Fix incorrect evict_size accumulation`, `Add Qwen3 model support`.
  - 나쁨: `fixes`, `update scheduler.py`, `WIP`.
- **커밋당 하나의 논리적 변경.** 리팩터링을 기능과 묶지 마세요.
- **PR 설명에 실행한 검증 명령을 포함**하여, 리뷰어가 재실행할 수 있도록.

## 다음 단계

- **[변경 사항 검증](./validating-changes)**: 변경이 실제로 동작함을 증명하는 방법.
- **[PR 워크플로우](./pr-workflow)**: 브랜치 모델, 출처 표기, 리뷰 기대치.
