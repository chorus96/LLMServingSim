# Llama-3.1-70B (파생 프로파일)

**이 프로파일은 측정된 것이 아니라 파생된 것입니다.** 동일 하드웨어
(`RTXPRO6000`)에서 측정된 `meta-llama/Llama-3.1-8B` 프로파일을 레이어별
FLOP/byte 모델로 해석적으로 스케일링하여 생성했으며, 다음 명령을 사용했습니다:

```bash
python profiler/tools/derive_profile.py --hardware RTXPRO6000 \
  --source meta-llama/Llama-3.1-8B --target meta-llama/Llama-3.1-70B --variant bf16
```

정확한 스케일링 계수는 `bf16/meta.yaml`의 `derived:` 블록을 참고하세요.
커널 실행 오버헤드, 텐서 코어 타일링, 대역폭 효과는 모델링되지 않으므로 절대
지연 시간은 근사값입니다. 측정된 프로파일이 마련되기 전까지 시뮬레이터가
70B 아키텍처를 실행할 수 있게 해줍니다(예: NELSSA 연구용). 실제 하드웨어에서
vLLM 프로파일러를 다시 실행하여 교체하세요.
