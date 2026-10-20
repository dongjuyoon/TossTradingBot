# TossTradingBot

미국 주식 스윙 전략과 로컬 AI의 추가 가치를 거래비용 차감 후 검증하기 위한 연구용 시스템입니다.

현재 구현 범위는 **Phase 1(토스증권 읽기 전용 시장 데이터)** 입니다. 실거래 주문 코드는 없으며 실행 모드는 `PAPER`로 고정되어 있습니다.

## 빠른 시작

```bash
source .venv/bin/activate
python -m pip install -e '.[dev]'
python scripts/check_environment.py
python scripts/check_ollama.py
python scripts/check_toss_api.py
python scripts/run_market_data.py AAPL --count 20
pytest
ruff check .
```

`qwen3:8b`가 없다면 사용자가 직접 `ollama pull qwen3:8b`를 실행한 뒤 Ollama 진단을 다시 수행합니다. 토스 인증 검사는 `.env.example`을 참고해 로컬 `.env`를 준비한 후 명시적으로 실행하며, Phase 0에서는 시세 조회나 주문을 전송하지 않습니다.

검증 결과는 [환경 보고서](docs/environment_report.md), [토스 API 역량표](docs/api_capabilities.md), [Phase 1 보고서](docs/phase1_report.md)에 정리되어 있습니다.
