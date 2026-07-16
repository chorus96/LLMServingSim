---
sidebar_position: 6
title: PR 워크플로우
---

# PR 워크플로우

기여가 당신의 fork에서 `main`으로 가는 방법. 한 번 읽으세요; 이후 각 PR은 실제 작업 위에
약 10분의 프로세스 오버헤드가 걸릴 것입니다.

## 브랜치 모델

- **`main`**: 활성 개발 브랜치. 모든 PR이 여기에 착지합니다.
- **Artifact 브랜치**: 논문별 재현성 브랜치, 발표처를 따라 명명됨(예:
  `ispass26-artifact`). **이것들에 대해 PR을 열지 마세요.** artifact 제출 상태에
  고정되어 있습니다.
- **당신의 작업**: `main`에서 분기한 feature 브랜치, 서술적으로
  명명됨(`add-deepseek-v3`, `fix-evict-accumulation`, `docs-cluster-config`). 권한이
  있어도 `main`에 직접 푸시하지 마세요.

```bash
git checkout main
git pull
git checkout -b add-deepseek-v3
```

## 커밋 위생

- **짧은 명령형 한 줄.** 기존 로그와 같은 스타일: `Fix incorrect evict_size
  accumulation`, `Add Qwen3 model support`, `Document MoE expert routing`.
- **커밋당 하나의 논리적 변경.** 같은 커밋의 리팩터링과 기능은 리뷰어의 악몽입니다.
- **발행된 커밋을 amend하지 마세요.** 푸시했으면, 새 커밋으로 후속하세요. 브랜치
  force-push는 리뷰 시작 *전에는* 괜찮지만, 일반적으로 이후에는 아닙니다.
- pre-commit 훅을 우회하기 위한 **`--no-verify` 없음.** 실패한 것을 고치세요.
- 누군가 정말로 이 커밋에서 당신과 pair-program하지 않은 한 **`Co-authored-by` 없음.**

좋은 커밋 메시지:

```
Fix evict_size accumulation when prefix cache spills to CPU

Spilling counted the block twice: once in the NPU eviction and
again when the second-tier pool inserted it. Drop the second
increment; the test in single_node_memory_instance.json now
matches the bench reference.
```

나쁜 것:

```
fixes
```

## 푸시하기 전에

체크리스트를 훑어보세요:

1. **Smoke 실행 통과.** **[변경 사항 검증](./validating-changes)**, 단계 1 참고.
2. 건드린 것에 대해 **표적 시나리오 통과.** 단계 2.
3. 변경이 end-to-end 정확도에 영향을 주면 **bench 검증이 회귀하지 않음.** 단계 3.
4. **규약 체크리스트**: `getattr` 폴백, `head_dim` 처리, 영어만, 레이어 이름,
   `astra-sim/inputs/` 편집 없음. **[코딩 규약](./conventions)** 참고.
5. 동작이 변경되었으면 **문서 업데이트.** `docs/` 아래 관련 페이지, 그리고 해당되면
   모듈의 `README.md`.
6. diff에 **머신별 경로나 생성 파일 없음.** `git diff --stat`과 `git diff --check`로
   sanity-check.

## PR 열기

fork(또는 직접 접근이 있으면 브랜치)에 푸시:

```bash
git push -u origin add-deepseek-v3
```

그런 다음 `casys-kaist/LLMServingSim:main`에 대해 PR을 여세요. 설명에 포함해야 할 것:

```
## What this changes

사용자에게 보이는 변경의 1-3문장 요약.

## Why

동기: 수정하는 버그, 활성화하는 기능, 물을 수 있게 하는 연구 질문.

## Validation

실행한 정확한 명령과 핵심 결과. 예를 들어:

  ./bench/examples/validate.sh Llama-3.1-8B
  -> TTFT MAPE 2.1% (was 2.3%), TPOT 1.7% (unchanged)

## Notes

미묘한 것: 알려진 제한, 관련 이슈, 의도적으로 포함하지 않은 후속.
```

무거운 템플릿은 필요 없습니다. Validation 섹션이 협상 불가한 한 부분입니다: 리뷰어에게
재실행할 구체적인 것을 주고 git 로그에 무엇이 확인되었는지의 기록을 줍니다.

## 리뷰가 어떻게 보이나

- **초기 응답**: 보통 첫 라운드에 2-3일 내. KAIST(UTC+9)와의 시간대 겹침이 도움이 되지만
  필수는 아닙니다.
- **리뷰어**: 주요 기여자 중 최소 한
  명([@JaehongCho](https://github.com/JaehongCho),
  [@hmchoi](https://github.com/hmchoi))과 건드린 영역을 소유한 사람. 문서 전용 PR은 하나의
  승인이면 충분합니다.
- **무엇이 blocked vs nit-pick되나**:
  - **Blocker**: ~5%를 넘는 bench 회귀, 깨진 smoke 실행, "이것을 결코 하지 마라" 목록의
    규약 위반, 새 플래그의 누락된 문서.
  - **Nit**: 명명, 코드 스타일 선호, 문서 표현. 리뷰어가 "nit:"이라고 말하거나 GitHub
    라벨을 사용합니다. 동의하면 처리하세요; 동의하지 않으면 한 문장으로 미루세요.
- **대화 스타일**: 간결하고 직접적. "This won't work for MoE"는 인신공격이 아닙니다;
  정중한 버전보다 빠릅니다. 마찬가지로 답하세요.

## Squash, rebase, 또는 merge?

프로젝트는 대부분의 PR을 `main`의 단일 커밋으로 squash하며, PR 제목이 커밋 메시지가
됩니다. 미리 브랜치의 중간 커밋을 정리할 필요가 없습니다. PR이 진정으로 여러 커밋으로
최선이면(예: 리팩터링 + 그것에 의존하는 기능), 설명에 그렇게 말하면 maintainer가 squash
대신 rebase합니다.

## 출처 표기

외부 기여자는 두 곳에서 credit을 받습니다:

1. **GitHub 커밋 이력**: merge 시 당신의 authorship이 보존됩니다.
2. **README 기여자 목록**: 기여가 사용자에게 보일 때(새 기능, 사소하지 않은 수정, 새
   모델이나 하드웨어 타깃), maintainer가 기존 `[@waneon]`, `[@HyunsuYEE]`, `[@junwha]`,
   `[@gleb-kun]` 패턴을 따라 GitHub 핸들 링크로 당신을 credit하는 라인을 README의
   "Highlights" 섹션에 추가합니다.

PR에서 자신을 기여자 목록에 추가할 필요가 없습니다. maintainer가 merge 시 추가합니다.

## Merge 후

- 다음 변경을 시작하기 전에 **`main`을 pull.** 로컬 브랜치가 더 이상 권위 있지 않습니다.
- **merge된 브랜치를 삭제** — 로컬과 원격 모두(GitHub이 merge 후 버튼을 제공; 로컬은 `git
  branch -d add-deepseek-v3`).
- **`main`의 CI를 하루나 이틀 주시.** PR이 잡지 못한 무언가가 깨졌으면, 당신이 그것을
  빨리 고칠 최적의 위치에 있습니다.

## 문제가 생길 때

- **내 PR이 리뷰 없이 일주일 방치됨.** 한 줄로 PR을 ping하세요. maintainer가 알림을 놓치기도
  합니다.
- **리뷰어가 동의하지 않는 변경을 요청함.** 댓글에 당신의 논리를 설명하세요. 리뷰어의 답
  이후에도 여전히 동의하지 않으면, tiebreaker를 위해 다른 주요 기여자를 태그하여
  escalate하세요. 잘못된 설계를 착지시키기보다 논의를 하는 것을 선호합니다.
- **내 변경이 예상보다 bench를 회귀시킴.** merge하지 마세요. PR을 draft로 열고 설명에
  회귀를 태그하세요; 그것이 당신의 변경, 기존 베이스라인, 또는 검증 방법론의 버그인지
  함께 알아낼 것입니다.
- **`main`에서 무언가를 깨뜨림.** 일어나는 일입니다. `Fix ...` 커밋으로 후속 PR을
  여세요; `main`에 `git push --force`하지 마세요.

## 다음 단계

이제 전체 그림을 얻었습니다. starter 이슈를 고르거나 제목에 `[contributor]`를 넣어 작업하고
싶은 것을 논의하는 새 이슈를 여세요.

환영합니다.
