import requests
import os
import yaml
import time

class CapitalAPI:
    def __init__(self):
        with open("config.yaml") as f:
            config = yaml.safe_load(f)
        self.base_url = config["capital_com"]["api_url"]
        # Use environment variables for sensitive data
        self.identifier = os.environ.get("CAPITAL_IDENTIFIER")
        self.password = os.environ.get("CAPITAL_PASSWORD")
        self.api_key = os.environ.get("CAPITAL_DEMO_API_KEY")
        if not self.identifier or not self.password:
            raise Exception("Missing CAPITAL_IDENTIFIER or CAPITAL_PASSWORD environment variables")
        self.session = requests.Session()
        self.session.headers.update({
            "X-CAP-API-KEY": self.api_key,
            "Content-Type": "application/json"
        })
        self.authenticate()

    def authenticate(self):
        resp = self.session.post(f"{self.base_url}session", json={
            "identifier": self.identifier,
            "password": self.password
        })
        if resp.status_code != 200:
            raise Exception(f"Auth failed: {resp.text}")
        cst = resp.headers.get("CST")
        xst = resp.headers.get("X-SECURITY-TOKEN")
        if cst and xst:
            self.session.headers.update({"CST": cst, "X-SECURITY-TOKEN": xst})

    def get_account_info(self):
        resp = self.session.get(f"{self.base_url}accounts")
        return resp.json()

    def get_historical_prices(self, epic, resolution, max_bars=100):
        """epic e.g., 'EURUSD', resolution e.g., 'MINUTE_5'"""
        url = f"{self.base_url}prices/{epic}?resolution={resolution}&max={max_bars}"
        resp = self.session.get(url)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("prices", [])
        else:
            print(f"Failed to fetch prices for {epic}: {resp.text}")
            return []

    def get_current_spread(self, epic):
        """Get current bid/ask from the latest tick (may not be live in demo REST)"""
        prices = self.get_historical_prices(epic, "MINUTE", 1)
        if prices:
            last = prices[0]
            bid = last["bidPrice"]["bid"]
            ask = last["askPrice"]["ask"]
            return bid, ask
        return None, None
