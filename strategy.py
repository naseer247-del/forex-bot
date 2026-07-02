import numpy as np

class StrategyEngine:
    def __init__(self, config):
        self.timeframes = list(config["trading"]["timeframes"].keys())
        self.pairs = config["trading"]["pairs"]
        self.min_bars = config["trading"]["min_bars"]

    def analyze(self, pair, ohlc_data):
        if not self._has_enough_data(ohlc_data):
            return None
        d_trend = self._trend(ohlc_data["D"])
        h4_trend = self._trend(ohlc_data["H4"])
        if d_trend == 0 or d_trend != h4_trend:
            return None
        h1 = ohlc_data["H1"]
        m15 = ohlc_data["m15"]
        mss_direction = self._detect_mss(h1)
        if mss_direction != d_trend:
            return None
        ob_level = self._find_order_block(h1, d_trend)
        if ob_level is None:
            return None
        current_price = m15[-1]["close"]
        if not self._price_in_zone(current_price, ob_level, 2):
            return None
        fvg_present = self._has_fvg(h1, d_trend) or self._has_fvg(m15, d_trend)
        sweep = self._detect_sweep(m15, ob_level, d_trend)
        vsa_signal = self._vsa_confirm(m15, d_trend)
        engulf = self._engulfing_at_ob(m15, ob_level, d_trend)
        score = 0
        score += 2  # D trend alignment
        score += 2  # H4 trend alignment
        score += 2 if ob_level else 0
        score += 1 if fvg_present else 0
        score += 2 if sweep else 0
        score += 1 if vsa_signal else 0
        score += 1 if engulf else 0
        if score >= 8:
            return {
                "pair": pair,
                "direction": d_trend,
                "entry": current_price,
                "stop_loss": self._calculate_sl(ob_level, d_trend, m15),
                "take_profit": self._calculate_tp(ob_level, d_trend, m15),
                "score": score,
                "timestamp": m15[-1]["timestamp"]
            }
        return None

    def _has_enough_data(self, ohlc_data):
        for tf in self.timeframes:
            if tf not in ohlc_data or len(ohlc_data[tf]) < self.min_bars:
                return False
        return True

    def _trend(self, candles):
        closes = [c["close"] for c in candles[-50:]]
        if len(closes) < 50:
            return 0
        sma50 = sum(closes) / 50
        return 1 if candles[-1]["close"] > sma50 else -1

    def _detect_mss(self, candles):
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        last_high = max(highs[-20:-5]) if len(highs) >= 20 else max(highs[:-5])
        last_low = min(lows[-20:-5]) if len(lows) >= 20 else min(lows[:-5])
        recent_high = max(highs[-5:])
        recent_low = min(lows[-5:])
        if recent_low < last_low - 0.0002 and candles[-1]["close"] > last_high:
            return 1
        if recent_high > last_high + 0.0002 and candles[-1]["close"] < last_low:
            return -1
        return 0

    def _find_order_block(self, candles, direction):
        for i in range(len(candles)-2, 10, -1):
            if direction == 1:
                if candles[i]["close"] < candles[i]["open"] and candles[i+1]["close"] > candles[i+1]["open"] and (candles[i+1]["high"] - candles[i+1]["low"]) > 0.3*np.std([c["high"]-c["low"] for c in candles]):
                    return candles[i]["open"]
            else:
                if candles[i]["close"] > candles[i]["open"] and candles[i+1]["close"] < candles[i+1]["open"] and (candles[i+1]["high"] - candles[i+1]["low"]) > 0.3*np.std([c["high"]-c["low"] for c in candles]):
                    return candles[i]["open"]
        return None

    def _price_in_zone(self, price, level, pip_tolerance=2):
        return abs(price - level) <= pip_tolerance * 0.0001

    def _has_fvg(self, candles, direction):
        for i in range(len(candles)-3, 2, -1):
            c1 = candles[i]
            c3 = candles[i+2]
            if direction == 1:
                if c1["high"] < c3["low"]:
                    return True
            else:
                if c1["low"] > c3["high"]:
                    return True
        return False

    def _detect_sweep(self, candles, level, direction):
        for c in candles[-5:]:
            if direction == 1:
                if c["low"] < level - 0.0002 and c["close"] > level:
                    return True
            else:
                if c["high"] > level + 0.0002 and c["close"] < level:
                    return True
        return False

    def _vsa_confirm(self, candles, direction):
        if len(candles) < 10:
            return False
        last = candles[-1]
        avg_vol = np.mean([c["tickVolume"] for c in candles[-10:]])
        body = abs(last["close"] - last["open"])
        range_candle = last["high"] - last["low"]
        if range_candle == 0:
            return False
        if body < 0.3*range_candle and last["tickVolume"] > 1.2*avg_vol:
            return True
        return False

    def _engulfing_at_ob(self, candles, level, direction):
        if len(candles) < 2:
            return False
        c1 = candles[-2]
        c2 = candles[-1]
        if not self._price_in_zone(c2["close"], level):
            return False
        if direction == 1:
            if c1["close"] < c1["open"] and c2["close"] > c2["open"] and c2["open"] < c1["close"] and c2["close"] > c1["open"]:
                return True
        else:
            if c1["close"] > c1["open"] and c2["close"] < c2["open"] and c2["open"] > c1["close"] and c2["close"] < c1["open"]:
                return True
        return False

    def _calculate_sl(self, ob_level, direction, candles):
        if direction == 1:
            lows = [c["low"] for c in candles[-10:]]
            swing_low = min(lows)
            return swing_low - 0.0002
        else:
            highs = [c["high"] for c in candles[-10:]]
            swing_high = max(highs)
            return swing_high + 0.0002

    def _calculate_tp(self, ob_level, direction, candles):
        sl = self._calculate_sl(ob_level, direction, candles)
        risk = abs(ob_level - sl)
        if direction == 1:
            return ob_level + 2 * risk
        else:
            return ob_level - 2 * risk
