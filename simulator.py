import json
import os

class Simulator:
    def __init__(self, state_file="state.json"):
        self.state_file = state_file
        self.state = self.load_state()

    def load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file) as f:
                return json.load(f)
        return {
            "equity": 1000.0,
            "peak_equity": 1000.0,
            "open_positions": [],
            "trades": [],
            "daily_pnl": 0.0,
            "start_time": "",
            "live_approved": False
        }

    def save_state(self, new_state):
        with open(self.state_file, "w") as f:
            json.dump(new_state, f, indent=2)

    def update_equity(self, pl):
        self.state["equity"] += pl
        if self.state["equity"] > self.state["peak_equity"]:
            self.state["peak_equity"] = self.state["equity"]
        today_str = self._today_str()
        last_day = self.state.get("last_day", "")
        if last_day != today_str:
            self.state["daily_pnl"] = 0.0
            self.state["last_day"] = today_str
        self.state["daily_pnl"] += pl

    def open_simulated_trade(self, signal, risk_amount):
        trade = {
            "id": len(self.state["trades"]) + 1,
            "pair": signal["pair"],
            "direction": signal["direction"],
            "entry": signal["entry"],
            "stop_loss": signal["stop_loss"],
            "take_profit": signal["take_profit"],
            "risk_amount": risk_amount,
            "open_time": signal["timestamp"],
            "status": "open"
        }
        self.state["open_positions"].append(trade)
        return trade

    def check_exits(self, latest_prices):
        for pos in self.state["open_positions"][:]:
            if pos["pair"] not in latest_prices:
                continue
            price = latest_prices[pos["pair"]]
            if pos["direction"] == 1:
                if price <= pos["stop_loss"]:
                    self._close_position(pos, -1.0)
                elif price >= pos["take_profit"]:
                    self._close_position(pos, 2.0)
            else:
                if price >= pos["stop_loss"]:
                    self._close_position(pos, -1.0)
                elif price <= pos["take_profit"]:
                    self._close_position(pos, 2.0)

    def _close_position(self, pos, r_multiple):
        pl = pos["risk_amount"] * r_multiple
        self.update_equity(pl)
        self.state["trades"].append({
            "pair": pos["pair"],
            "direction": pos["direction"],
            "entry": pos["entry"],
            "exit_reason": "sl" if r_multiple < 0 else "tp",
            "r_multiple": r_multiple,
            "timestamp": pos["open_time"]
        })
        self.state["open_positions"].remove(pos)

    def _today_str(self):
        from datetime import datetime
        return datetime.utcnow().strftime("%Y-%m-%d")
