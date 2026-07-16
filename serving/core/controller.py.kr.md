# `serving/core/controller.py` 분석

**ASTRA-Sim 서브프로세스와의 IPC 프로토콜**을 관리하는 모듈입니다. 워크로드 그래프
경로를 stdin으로 보내고 stdout에서 반복 타이밍(사이클 수)을 파싱합니다.

## 개요

| 항목 | 내용 |
| --- | --- |
| 역할 | ASTRA-Sim subprocess와 stdin/stdout 기반 통신 |
| 클래스 | `Controller` |
| 상태 | `end_dict` — NPU별 마지막 완료 iteration id |

## 블록 다이어그램

```mermaid
flowchart LR
    SIM["시뮬레이터<br/>(scheduler)"] -->|write_flush(workload_path)| STDIN[[ASTRA-Sim stdin]]
    STDIN --> ASTRA["ASTRA-Sim<br/>(C++ 서브프로세스)"]
    ASTRA --> STDOUT[[ASTRA-Sim stdout]]
    STDOUT -->|read_wait| RW["'Waiting' 라인까지 읽기"]
    STDOUT -->|check_end| CE["'All Request Has Been Exited' 확인"]
    STDOUT -->|parse_output| PO["정규식으로<br/>sys/id/cycle/com_cycle 추출"]
    PO --> SIM
```

## 주요 구성 요소

| 메서드 | 역할 |
| --- | --- |
| `read_wait(p)` | stdout를 `"Waiting"` 또는 `"Checking Non-Exited Systems ..."` 라인까지 읽어 반환 |
| `check_end(p)` | 모든 요청 종료(`All Request Has Been Exited`) 또는 오류 라인까지 대기 |
| `write_flush(p, input)` | 워크로드 경로 등을 stdin에 쓰고 flush |
| `parse_output(output)` | `sys[N] iteration M finished, C cycles, exposed communication X cycles.` 정규식으로 `{sys, id, cycle}` 추출; 새 완료 시 로깅 |

## 참고

- `end_dict`로 각 NPU의 이전 완료 iteration을 추적해 중복 로깅을 방지합니다.
- 블로킹 방식(라인이 나타날 때까지 `readline`)으로 ASTRA-Sim과 동기화합니다.
