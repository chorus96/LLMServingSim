# configs/pim

DRAMSim3 INI 형식의 PIM(Processing-In-Memory) 장치 설정 파일입니다.
`pim_model.py`가 PIM 어텐션 지연 시간과 전력 파라미터를 계산하는 데 사용합니다.

클러스터 설정의 `cpu_mem` 섹션에 `pim_config`를 지정하고 `python -m serving`에
`--enable-attn-offloading`을 전달하여 PIM을 활성화합니다.

## 제공되는 설정

| 설정 | 프로토콜 | 용량 | 속도 | 설명 |
| --- | --- | --- | --- | --- |
| `DDR4_8GB_3200_pim.ini` | DDR4 | 8 GB | 3200 MT/s | DDR4 PIM 모듈 |
| `HBM2_1GB_2000_pim.ini` | HBM2 | 1 GB | 2000 MT/s | HBM2 PIM 모듈 |
| `LPDDR4X_2GB_4266_pim.ini` | LPDDR4X | 2 GB | 4266 MT/s | LPDDR4X PIM 모듈 |
| `LPDDR5_2GB_6400_pim.ini` | LPDDR5 | 2 GB | 6400 MT/s | LPDDR5 PIM 모듈 |
| `DDR5_1TB_6400_pim.ini` | DDR5 | 1 TB | 6400 MT/s | NELSSA HC-PNM 모듈 (4채널, ~200 GB/s) |
| `LPDDR5_HBPNM_128GB_pim.ini` | LPDDR5X | 128 GB | 8533 MT/s | HB-PNM 모듈 / CXL-PNM [4] 베이스라인 (~1.1 TB/s, 용량 제한) |

## 주요 파라미터

시뮬레이터는 INI 파일에서 다음을 추출합니다:

- **대역폭(Bandwidth)**: `device_width`, `BL`, `tCK`, 채널 수에서 유도
- **지연 시간(Latency)**: 타이밍 파라미터(`tRCD`, `CL` 등)에서 유도
- **용량(Capacity)**: `rows * columns * device_width * banks * bankgroups`
- **PIM 유형**: `[dram_structure]` 섹션의 `pim_type` (`SINGLE` 또는 `DUAL`)
