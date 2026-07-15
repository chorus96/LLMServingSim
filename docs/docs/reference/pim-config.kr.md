---
sidebar_position: 3
title: PIM 설정
---

# PIM 설정 스키마

PIM(Processing-In-Memory) 장치 설정은 **DRAMSim3 INI 형식**으로
`configs/pim/<name>.ini`에 있습니다. `--enable-attn-offloading`이 켜지면
시뮬레이터의 `pim_model.py`가 이를 읽어 PIM 측 어텐션 지연 시간을 계산합니다.

## 파일 위치

```
configs/pim/
├── DDR4_8GB_3200_pim.ini
├── HBM2_1GB_2000_pim.ini
├── LPDDR4X_2GB_4266_pim.ini
├── LPDDR5_2GB_6400_pim.ini
└── README.md
```

클러스터 설정은 노드의 `cpu_mem.pim_config` 필드(`.ini` 확장자 없이)를 통해 이 중
하나를 참조합니다:

```json
"cpu_mem": {
  "mem_size": 512,
  "mem_bw": 256,
  "mem_latency": 0,
  "pim_config": "DDR4_8GB_3200_pim"
}
```

## 번들된 설정

| 파일 | 프로토콜 | 용량 | 속도 | 비고 |
| --- | --- | --- | --- | --- |
| `DDR4_8GB_3200_pim.ini` | DDR4 | 8 GB | 3200 MT/s | 표준 DDR4 PIM 모듈 |
| `HBM2_1GB_2000_pim.ini` | HBM2 | 1 GB | 2000 MT/s | HBM2 PIM(고대역폭) |
| `LPDDR4X_2GB_4266_pim.ini` | LPDDR4X | 2 GB | 4266 MT/s | 모바일급 PIM |
| `LPDDR5_2GB_6400_pim.ini` | LPDDR5 | 2 GB | 6400 MT/s | 모바일급 PIM, 더 빠름 |

## INI 구조

각 PIM 설정은 세 섹션을 가집니다.

### `[dram_structure]`

```ini
[dram_structure]
protocol = DDR4
bankgroups = 2
banks_per_group = 4
rows = 65536
columns = 1024
device_width = 16
BL = 8
pim_type = SINGLE
```

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `protocol` | string | DRAM 표준. `DDR4`, `DDR5`, `HBM2`, `HBM3`, `LPDDR4`, `LPDDR4X`, `LPDDR5` |
| `bankgroups` | int | 장치당 bank group |
| `banks_per_group` | int | bank group당 bank |
| `rows` | int | bank당 row |
| `columns` | int | row당 column |
| `device_width` | int | 비트 단위 장치 데이터 폭(일반적으로 4 / 8 / 16) |
| `BL` | int | Burst length |
| `pim_type` | enum | `SINGLE`(채널당 PIM 유닛 하나) 또는 `DUAL`(채널당 유닛 둘) |

시뮬레이터는 다음을 계산합니다:

- `device_width × BL × tCK × channel_count`에서 **대역폭**.
- `rows × columns × device_width × banks × bankgroups`에서 **용량**.

### `[timing]`

```ini
[timing]
tCK = 0.63          # 클럭 주기(ns)
CL = 22             # CAS latency
CWL = 16            # CAS write latency
tRCD = 22           # RAS-to-CAS delay
tRP = 22            # row precharge time
tRAS = 52           # row active time
tRFC = 560          # refresh cycle
tREFI = 12480       # refresh interval
tRRD_S = 9          # row-to-row delay (다른 bank group)
tRRD_L = 11         # row-to-row delay (같은 bank group)
tWTR_S = 4          # write-to-read delay (다른 bank group)
tWTR_L = 12         # write-to-read delay (같은 bank group)
tFAW = 48           # four-activate window
tWR = 24            # write recovery
tRTP = 12           # read-to-precharge delay
tCCD_S = 4          # CAS-to-CAS (다른 bank group)
tCCD_L = 8          # CAS-to-CAS (같은 bank group)
```

모든 타이밍 파라미터는 명시적으로 다르게 명명되지 않는 한 **클럭 사이클** 단위입니다
(`tCK`는 ns 단위). 전체 목록은 DRAMSim3의 스펙을 반영합니다. 시뮬레이터는 PIM 접근
모델링을 위해 지연 관련 부분집합을 추출합니다.

전체 DRAMSim3 타이밍 의미론은
[DRAMSim3 문서](https://github.com/umd-memsys/DRAMsim3)를 참고하세요.

### `[system]`

```ini
[system]
channel_size = 8192
channels = 1
bus_width = 64
address_mapping = rorabgbachco
queue_structure = PER_BANK
row_buf_policy = OPEN_PAGE
```

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `channel_size` | int | MB 단위 채널별 용량 |
| `channels` | int | 메모리 채널 수(PIM 계산은 채널별로 발생) |
| `bus_width` | int | 비트 단위 메모리 버스 폭 |
| `address_mapping` | string | DRAMSim3 주소 매핑 방식 |
| `queue_structure` | enum | 큐잉 정책(`PER_BANK`, `PER_CHANNEL` 등) |
| `row_buf_policy` | enum | Row buffer 정책(`OPEN_PAGE`, `CLOSE_PAGE`) |

`channels`는 가장 시뮬레이터 관련성이 높은 필드입니다: 채널이 많을수록 어텐션
스텝당 병렬 PIM 계산이 많아집니다. 트레이스 생성기는 병렬 실행을 위해 어텐션 head를
채널에 분배합니다.

## 새 PIM 설정 추가

1. 새 `.ini` 파일을 `configs/pim/<name>.ini`에 넣기.
2. 위의 세 섹션을 채우기. 올바른 형태는 번들된 설정을 참조.
3. 클러스터 설정에서 참조: `"cpu_mem": {"pim_config": "<name>"}`.
4. `--enable-attn-offloading`으로 실행.

DRAMSim3 타이밍 파라미터는 모델링하려는 특정 DRAM 부품의 JEDEC 데이터시트나 벤더
스펙에서 가져올 수 있습니다.

## 이것이 사용되는 곳

- **`serving/core/pim_model.py`**: INI를 로드하고 타이밍 파라미터를 트레이스
  생성기에 노출.
- **`serving/core/trace_generator.py`**: `--enable-attn-offloading`이 켜지면 NPU
  어텐션을 로드된 모델로 계산한 PIM 어텐션으로 교체.
- **전력 모델**: 클러스터 설정에 `power:` 블록이 있으면, PIM 에너지가 채널
  수(채널당 PIM 유닛 하나 × 채널별 전력)를 통해 회계 처리됨.

전체 PIM offload 메커니즘은 **[시뮬레이터 → PIM
offload](/docs/simulator/specialized/pim-offload)**를 참고하세요. 작동 예제는
**[예제 → PIM 어텐션 offload](/docs/examples/disaggregated/pim-attention-offload)**를
참고하세요.

## 함정

1. **번들된 네 INI 파일 모두 `pim_type = SINGLE`을 사용합니다.** `DUAL`로 전환하면
   채널별 PIM 계산 용량이 두 배가 되지만, 클러스터 설정의 전력 모델 항목에서
   `pim_type = DUAL`이 지원되어야 합니다.
2. **`channels = N`이 N개의 독립 PIM 장치를 의미하지 않습니다.** 시뮬레이터는 하나의
   PIM 장치 내 채널별 병렬성을 모델링합니다. 여러 PIM 장치의 경우 여러 노드를
   설정하겠지만, 그것은 다른 토폴로지입니다.
3. **INI는 DRAMSim3 표준으로 파싱됩니다.** 시뮬레이터 로더가 모르는 커스텀 필드를
   추가하지 마세요; 무시됩니다.

## 다음 단계

- **[클러스터 설정 → `cpu_mem.pim_config`](./cluster-config#cpu_mem)** — 이 파일을
  클러스터에 연결하는 방법.
- **[시뮬레이터 → PIM offload](/docs/simulator/specialized/pim-offload)** —
  시뮬레이션 시점에 무슨 일이 일어나는지.
