class RiskManager:
    def __init__(self, config):
        self.max_risk_pct = config["risk"]["max_risk_per_trade_pct"]
        self.max_daily_loss_pct = config["risk"]["max_daily_loss_pct"]
        self.max_open = config["risk"]["max_open_positions"]
        self.max_corr_usd = config["risk"]["max_correlated_usd_pairs"]

    def can_open_trade(self, open_positions, equity, daily_pnl):
        if len(open_positions) >= self.max_open:
            return False
        if equity <= 0:
            return False
        if daily_pnl < -equity * self.max_daily_loss_pct:
            return False
        usd_pairs = [p for p in open_positions if "USD" in p["pair"]]
        if len(usd_pairs) >= self.max_corr_usd:
            return False
        return True

    def calculate_position_size(self, equity, stop_distance_pips, pair):
        risk_amount = equity * self.max_risk_pct
        return risk_amount
