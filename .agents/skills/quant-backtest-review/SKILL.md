---
name: quant-backtest-review
description: Review this project's quantitative strategies and backtests for correctness, costs, reproducibility, and temporal leakage. Use when strategy or backtest code or results change.
---

# Quant backtest review

Require deterministic inputs, configuration capture, and separate in-sample/out-of-sample or walk-forward periods.

- Verify signals use only information available before the simulated decision.
- Model next-eligible execution, commissions, spread, slippage, FX cost, and turnover.
- Check corporate actions, survivorship, calendars, time zones, and missing bars.
- Keep Quant Only, Quant + AI, and Quant + AI + Reflection on identical data, costs, and risk budgets.
- Reject historical news/AI claims when point-in-time source data is unavailable.
- Test that reflections created after a trade cannot enter earlier prompts.
- Report parameter sensitivity and regime results, not only the best parameter set.
