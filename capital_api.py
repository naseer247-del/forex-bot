import requests
import os
import yaml
import time

class CapitalAPI:
    def __init__(self):
        with open("config.yaml") as f:
            config = yaml.safe_load(f)
        self.base_url = config["capital_com"]["api_url"]
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
        try:
            resp = self.session.post(f"{self.base_url}session", json={
                "identifier": self.identifier,
                "password": self.password
            }, timeout=10)
            if resp.status_code != 200:
                raise Exception(f"Auth failed: {resp.text}")
            cst = resp.headers.get("CST")
            xst = resp.headers.get("X-SECURITY-TOKEN")
            if cst and xst:
                self.session.headers.update({"CST": cst, "X-SECURITY-TOKEN": xst})
        except Exception as e:
            print(f"Authentication error: {e}")
            raise

    def get_account_info(self):
        try:
            resp = self.session.get(f"{self.base_url}accounts", timeout=10)
            return resp.json()
        except Exception as e:
            print(f"Failed to get account info: {e}")
            return {}

    def get_historical_prices(self, epic, resolution, max_bars=60):
        """epic e.g., 'EURUSD', resolution e.g., 'MINUTE_5'"""
        url = f"{self.base_url}prices/{epic}?resolution={resolution}&max={max_bars}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                prices = data.get("prices", [])
                return prices
            else:
                print(f"Failed to fetch {epic} {resolution}: HTTP {resp.status_code}")
                return []
        except requests.exceptions.Timeout:
            print(f"Timeout fetching {epic} {resolution} after 10s")
            return []
        except Exception as e:
            print(f"Error fetching {epic} {resolution}: {e}")
            return []
