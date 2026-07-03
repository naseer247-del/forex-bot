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
            "live_approved": False,
            "last_run": {}
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

    def open_simulated_trade(self, signal, risk_amount, units=0.0):
        trade = {
            "id": len(self.state["trades"]) + 1,
            "pair": signal["pair"],
            "direction": signal["direction"],
            "entry": signal["entry"],
            "stop_loss": signal["stop_loss"],
            "take_profit": signal["take_profit"],
            "risk_amount": risk_amount,
            "units": units,
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
                    self._close_position(pos, pos["stop_loss"])  # stop
                elif price >= pos["take_profit"]:
                    self._close_position(pos, pos["take_profit"])  # tp
            else:
                if price >= pos["stop_loss"]:
                    self._close_position(pos, pos["stop_loss"])  # stop
                elif price <= pos["take_profit"]:
                    self._close_position(pos, pos["take_profit"])  # tp

    def _close_position(self, pos, exit_price):
        """
        Calculate P/L from units and price movement. Update equity and record the trade.
        P/L calculation (simplified):
          pl = units * (exit_price - entry) * direction_sign
        where direction_sign is +1 for long, -1 for short.
        r_multiple = pl / risk_amount (risk_amount stored on position)
        """
        direction = pos["direction"]
        entry = pos["entry"]
        units = pos.get("units", 0.0)
        risk_amount = pos.get("risk_amount", 0.0)

        # price difference favoring the position
        if direction == 1:
            price_diff = exit_price - entry
        else:
            price_diff = entry - exit_price

        pl = units * price_diff

        # Fallback: if units are zero, use classic r-multiple mapping (backwards compatible)
        if units == 0.0 and risk_amount != 0.0:
            # determine r_multiple based on stop vs exit
            # if exit equals take_profit we assume +2, stop -> -1
            if exit_price == pos.get("take_profit"):
                r_mult = 2.0
            else:
                r_mult = -1.0
            pl = risk_amount * r_mult
            r_multiple = r_mult
        else:
            r_multiple = (pl / risk_amount) if risk_amount != 0 else 0.0

        # update equity and records
        self.update_equity(pl)
        self.state["trades"].append({
            "pair": pos["pair"],
            "direction": pos["direction"],
            "entry": pos["entry"],
            "exit": exit_price,
            "exit_reason": "sl" if r_multiple < 0 else "tp",
            "r_multiple": r_multiple,
            "timestamp": pos.get("open_time")
        })
        try:
            self.state["open_positions"].remove(pos)
        except ValueError:
            pass

    def _today_str(self):
        from datetime import datetime
        return datetime.utcnow().strftime("%Y-%m-%d")

    def set_last_run(self, run_info):
        """Store a summary of the latest bot cycle."""
        self.state["last_run"] = run_info
