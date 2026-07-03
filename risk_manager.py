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

    def calculate_position_size(self, equity, stop_distance_price, pair):
        """
        Calculate position sizing using stop distance and an approximate pip value.

        Returns a dict with:
          - risk_amount: money to risk (equity * max_risk_pct)
          - units: approximate position units sized so that risk_amount ~= units * pip_value * stop_pips

        Notes:
        - stop_distance_price is a price difference (entry - stop_loss) in price units.
        - pip size is assumed 0.01 for JPY pairs, else 0.0001.
        - pip value per unit is approximated as 1 * pip_size (this is a simplification).
        - The simulator currently uses risk_amount for P/L calculations; units are stored for future use/clarity.
        """
        # money we are willing to risk
        risk_amount = equity * self.max_risk_pct

        # determine pip size
        pip_size = 0.01 if "JPY" in pair else 0.0001

        # compute stop distance in pips (guard against zero)
        stop_pips = max(1.0, abs(stop_distance_price) / pip_size)

        # approximate pip value per 1 unit (simplified)
        pip_value_per_unit = pip_size

        # units to trade so that units * pip_value_per_unit * stop_pips ~= risk_amount
        units = 0.0
        try:
            units = risk_amount / (stop_pips * pip_value_per_unit)
        except Exception:
            units = 0.0

        return {"risk_amount": risk_amount, "units": units}
