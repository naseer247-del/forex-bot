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

def main():
    if not is_trading_session():
        print("Outside trading session, skipping.")
        return

    api = CapitalAPI()
    simulator = Simulator()
    strategy = StrategyEngine(config)
    risk_mgr = RiskManager(config)
    portfolio = PortfolioManager(config)
    portfolio.update_from_state(simulator.state)

    # --- 1. Get latest M1 closing mid-price for all pairs (to check open positions) ---
    latest_m1 = {}
    for pair in config["trading"]["pairs"]:
        prices = api.get_historical_prices(pair, "MINUTE", 1)
        if prices:
            # Capital.com returns "closePrice": {"bid": ..., "ask": ...}
            cp = prices[0].get("closePrice", {})
            bid = cp.get("bid")
            ask = cp.get("ask")
            if bid and ask:
                latest_m1[pair] = (bid + ask) / 2.0   # mid-price
            elif bid:
                latest_m1[pair] = bid
            elif ask:
                latest_m1[pair] = ask
            else:
                # fallback: compute from snapshotTime if needed (rare)
                latest_m1[pair] = prices[0]["lastTradedVolume"]  # just in case, but this is volume
                # Actually we should not guess. We'll skip if no price.
                if pair in latest_m1 and not latest_m1[pair]:
                    del latest_m1[pair]

    # --- 2. Check for any closed positions (SL/TP hits) ---
    simulator.check_exits(latest_m1)

    # --- 3. Fetch multi-timeframe OHLC data for all pairs ---
    ohlc_cache = {}
    for pair in config["trading"]["pairs"]:
        pair_data = {}
        for tf, capital_res in config["trading"]["timeframes"].items():
            candles = api.get_historical_prices(pair, capital_res, config["trading"]["min_bars"])
            formatted = []
            for c in candles:
                # Extract bid/ask for OHLC and compute mid prices
                open_price = mid_or_fallback(c.get("openPrice", {}))
                high_price = mid_or_fallback(c.get("highPrice", {}))
                low_price  = mid_or_fallback(c.get("lowPrice", {}))
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
        ohlc_cache[pair] = pair_data

    # --- 4. Run strategy and open new trades ---
    for pair in config["trading"]["pairs"]:
        if pair not in ohlc_cache:
            continue
        signal = strategy.analyze(pair, ohlc_cache[pair])
        if signal is None:
            continue
        if risk_mgr.can_open_trade(simulator.state["open_positions"],
                                   simulator.state["equity"],
                                   simulator.state["daily_pnl"]):
            risk_amount = risk_mgr.calculate_position_size(simulator.state["equity"],
                                                           abs(signal["entry"] - signal["stop_loss"]), pair)
            simulator.open_simulated_trade(signal, risk_amount)
            print(f"Opened demo trade {pair} dir={signal['direction']}")

    # --- 5. Update portfolio performance ---
    portfolio.trades = simulator.state["trades"]
    if portfolio.is_live_approved():
        simulator.state["live_approved"] = True
        print("Live trading approved!")
    else:
        simulator.state["live_approved"] = False

    simulator.state["trades"] = portfolio.trades
    simulator.state["start_time"] = portfolio.start_time.isoformat()
    simulator.save_state(simulator.state)


def mid_or_fallback(price_dict):
    """Calculate mid price from bid/ask; if missing, return 0."""
    bid = price_dict.get("bid")
    ask = price_dict.get("ask")
    if bid and ask:
        return (bid + ask) / 2.0
    return bid or ask or 0.0


if __name__ == "__main__":
    main()
