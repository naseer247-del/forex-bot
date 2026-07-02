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

    latest_m1 = {}
    for pair in config["trading"]["pairs"]:
        prices = api.get_historical_prices(pair, "MINUTE", 1)
        if prices:
            latest_m1[pair] = prices[0]["closePrice"]["close"]

    simulator.check_exits(latest_m1)

    ohlc_cache = {}
    for pair in config["trading"]["pairs"]:
        pair_data = {}
        for tf, capital_res in config["trading"]["timeframes"].items():
            candles = api.get_historical_prices(pair, capital_res, config["trading"]["min_bars"])
            formatted = []
            for c in candles:
                formatted.append({
                    "timestamp": c["snapshotTime"],
                    "open": c["openPrice"]["open"],
                    "high": c["highPrice"]["high"],
                    "low": c["lowPrice"]["low"],
                    "close": c["closePrice"]["close"],
                    "tickVolume": c.get("lastTradedVolume", 100)
                })
            pair_data[tf] = formatted
        ohlc_cache[pair] = pair_data

    for pair in config["trading"]["pairs"]:
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

    portfolio.trades = simulator.state["trades"]
    if portfolio.is_live_approved():
        simulator.state["live_approved"] = True
        print("Live trading approved!")
    else:
        simulator.state["live_approved"] = False

    simulator.state["trades"] = portfolio.trades
    simulator.state["start_time"] = portfolio.start_time.isoformat()
    simulator.save_state(simulator.state)

if __name__ == "__main__":
    main()
