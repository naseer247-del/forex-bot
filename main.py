import os
import sys
import json
import time
from datetime import datetime
import pytz
import yaml
from capital_api import CapitalAPI
from strategy import StrategyEngine
from risk_manager import RiskManager
from portfolio_manager import PortfolioManager
from simulator import Simulator

with open("config.yaml") as f:
    config = yaml.safe_load(f)


def is_trading_session():
    now = datetime.now(pytz.timezone("UTC"))
    start = config["trading"]["session_start_utc"]
    end = config["trading"]["session_end_utc"]
    return start <= now.hour < end and now.weekday() < 5


def run_cycle(api, simulator, strategy, risk_mgr, portfolio):
    run_log = {
        "timestamp": datetime.utcnow().isoformat(),
        "session_active": False,
        "pairs_scanned": 0,
        "signals_found": 0,
        "trades_opened": 0,
        "errors": []
    }

    if not is_trading_session():
        run_log["session_active"] = False
        print("Outside trading session, skipping.")
        # Still save the run log so dashboard knows bot is alive
        simulator.set_last_run(run_log)
        simulator.save_state(simulator.state)
        return

    run_log["session_active"] = True

    # ensure portfolio reflects current state
    portfolio.update_from_state(simulator.state)

    # --- Fetch latest M1 prices ---
    latest_m1 = {}
    for pair in config["trading"]["pairs"]:
        try:
            prices = api.get_historical_prices(pair, "MINUTE", 1)
            if prices:
                cp = prices[0].get("closePrice", {})
                bid = cp.get("bid")
                ask = cp.get("ask")
                if bid and ask:
                    latest_m1[pair] = (bid + ask) / 2.0
        except Exception as e:
            run_log["errors"].append(f"Price fetch error {pair}: {str(e)}")

    simulator.check_exits(latest_m1)

    # --- Build OHLC cache and run strategy ---
    ohlc_cache = {}
    for pair in config["trading"]["pairs"]:
        pair_data = {}
        for tf, capital_res in config["trading"]["timeframes"].items():
            try:
                candles = api.get_historical_prices(pair, capital_res, config["trading"]["min_bars"])
                formatted = []
                for c in candles:
                    open_price = mid_or_fallback(c.get("openPrice", {}))
                    high_price = mid_or_fallback(c.get("highPrice", {}))
                    low_price = mid_or_fallback(c.get("lowPrice", {}))
                    close_price = mid_or_fallback(c.get("closePrice", {}))
                    volume = c.get("lastTradedVolume", 100)
                    formatted.append({
                        "timestamp": c["snapshotTime"],
                        "open": open_price,
                        "high": high_price,
                        "low": low_price,
                        "close": close_price,
                        "tickVolume": volume
                    })
                pair_data[tf] = formatted
            except Exception as e:
                run_log["errors"].append(f"OHLC error {pair} {tf}: {str(e)}")
        ohlc_cache[pair] = pair_data

    for pair in config["trading"]["pairs"]:
        if pair not in ohlc_cache:
            continue
        run_log["pairs_scanned"] += 1
        try:
            signal = strategy.analyze(pair, ohlc_cache[pair])
        except Exception as e:
            run_log["errors"].append(f"Strategy error {pair}: {str(e)}")
            continue

        if signal is not None:
            run_log["signals_found"] += 1
            if risk_mgr.can_open_trade(simulator.state["open_positions"],
                                       simulator.state["equity"],
                                       simulator.state["daily_pnl"]):
                pos_info = risk_mgr.calculate_position_size(simulator.state["equity"],
                                                           abs(signal["entry"] - signal["stop_loss"]),
                                                           pair)
                risk_amount = pos_info.get("risk_amount", 0.0)
                units = pos_info.get("units", 0.0)
                simulator.open_simulated_trade(signal, risk_amount, units)
                run_log["trades_opened"] += 1
                print(f"Opened demo trade {pair} dir={signal['direction']}")

    # --- Update portfolio ---
    portfolio.trades = simulator.state.get("trades", [])
    if portfolio.is_live_approved():
        simulator.state["live_approved"] = True
        print("Live trading approved!")
    else:
        simulator.state["live_approved"] = False

    simulator.state["trades"] = portfolio.trades
    simulator.state["start_time"] = portfolio.start_time.isoformat()
    simulator.set_last_run(run_log)
    simulator.save_state(simulator.state)


def mid_or_fallback(price_dict):
    bid = price_dict.get("bid")
    ask = price_dict.get("ask")
    if bid and ask:
        return (bid + ask) / 2.0
    return bid or ask or 0.0


def main():
    # create long-lived objects to reuse between cycles
    api = None
    simulator = None
    strategy = None
    risk_mgr = None
    portfolio = None

    try:
        api = CapitalAPI()
        simulator = Simulator()
        strategy = StrategyEngine(config)
        risk_mgr = RiskManager(config)
        portfolio = PortfolioManager(config)
        portfolio.update_from_state(simulator.state)

        cycle_seconds = config.get("trading", {}).get("cycle_seconds", 300)

        while True:
            start = time.time()
            run_cycle(api, simulator, strategy, risk_mgr, portfolio)
            elapsed = time.time() - start
            to_sleep = max(0, cycle_seconds - elapsed)
            # sleep in small increments to be responsive to KeyboardInterrupt
            end_time = time.time() + to_sleep
            while time.time() < end_time:
                time.sleep(min(1, end_time - time.time()))
    except KeyboardInterrupt:
        print("Stopping bot, saving state...")
        try:
            if simulator:
                simulator.save_state(simulator.state)
        except Exception:
            pass
    except Exception as e:
        print(f"Fatal error in main loop: {e}")
        try:
            if simulator:
                simulator.set_last_run({"timestamp": datetime.utcnow().isoformat(), "session_active": False, "errors": [str(e)]})
                simulator.save_state(simulator.state)
        except Exception:
            pass


if __name__ == "__main__":
    main()
