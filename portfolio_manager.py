from datetime import datetime, timedelta

class PortfolioManager:
    def __init__(self, config):
        self.min_win_rate = config["portfolio"]["demo_required_win_rate"]
        self.sample_size = config["portfolio"]["demo_sample_trades"]
        self.min_days = config["portfolio"]["min_demo_days"]
        self.start_time = datetime.utcnow()
        self.trades = []

    def update_from_state(self, state):
        self.trades = state.get("trades", [])
        self.start_time = datetime.fromisoformat(state.get("start_time", datetime.utcnow().isoformat()))

    def record_trade(self, pl_ratio):
        self.trades.append({
            "timestamp": datetime.utcnow().isoformat(),
            "pl_ratio": pl_ratio
        })
        if len(self.trades) > self.sample_size:
            self.trades = self.trades[-self.sample_size:]

    def is_live_approved(self):
        if len(self.trades) < self.sample_size:
            return False
        if (datetime.utcnow() - self.start_time).days < self.min_days:
            return False
        wins = [t for t in self.trades if t["pl_ratio"] > 0]
        win_rate = len(wins) / len(self.trades)
        return win_rate >= self.min_win_rate

    def get_state(self):
        return {
            "trades": self.trades,
            "start_time": self.start_time.isoformat()
        }
