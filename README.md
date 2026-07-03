# Forex Bot

Demo Python Forex trading bot and simulator. Scans configured pairs across multiple timeframes, scores signals using order-block / FVG / VSA heuristics, opens simulated trades and tracks equity in state.json. Intended for demo/backtest and milestone approval before live execution.

## Quick start

1. Install dependencies:

```
pip install -r requirements.txt
```

2. Required environment variables (Capital.com credentials):

- CAPITAL_IDENTIFIER
- CAPITAL_PASSWORD
- CAPITAL_DEMO_API_KEY

3. Configure bot in `config.yaml` (pairs, timeframes, session hours, risk limits).

4. Run the bot (runs continuously, cycles every 5 minutes):

```
python main.py
```

Recommended: run inside a screen/tmux or as a systemd service.

## Files of interest

- `main.py` — orchestrator, main loop (5-minute cycle)
- `strategy.py` — StrategyEngine: multi-timeframe filters and scoring
- `capital_api.py` — Capital.com REST wrapper (auth uses env vars)
- `simulator.py` — Local simulator, now uses `units` returned from position sizing to compute P/L
- `risk_manager.py` — Position sizing (returns `{risk_amount, units}`)
- `config.yaml` — All runtime config (trading, risk, portfolio)
- `state.json` — Persisted state and last_run summary used by the dashboard
- `index.html` — Simple dashboard that reads `state.json` and auto-refreshes every 5 minutes

## Notes and next steps

- `risk_manager.calculate_position_size` now returns both `risk_amount` and estimated `units`. This improves sizing but is an approximation — real pip-value depends on contract size and account currency.
- Simulator now computes P/L from `units * price_move`. If units is 0, it falls back to r-multiple mapping for compatibility.
- Live execution is not implemented. To go live, implement order placement in `capital_api.py` and integration in `portfolio_manager.py`.

