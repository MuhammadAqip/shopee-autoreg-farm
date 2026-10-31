"""proxy pool + sms/otp abstraction for the Shopee farm."""
import random
import time


class ProxyPool:
    """Rotating proxy list. One port per account -- never share a port inside a
    registration chain (Shopee flags a mid-session IP hop)."""

    def __init__(self, proxies: list[str] | None = None):
        self.proxies = proxies or []
        self._held: dict[str, str] = {}   # account_key -> proxy

    def add(self, proxy: str):
        self.proxies.append(proxy)

    def load_file(self, path: str):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    self.proxies.append(line)
        return len(self.proxies)

    def acquire(self, account_key: str) -> str | None:
        """Pin a proxy to an account; reuse on retry, never mid-chain."""
        if not self.proxies:
            return None
        if account_key in self._held:
            return self._held[account_key]
        p = random.choice(self.proxies)
        self._held[account_key] = p
        return p

    def release(self, account_key: str, failed: bool = False):
        if failed:
            self._held.pop(account_key, None)

    def __len__(self):
        return len(self.proxies)


class OTPSink:
    """Base class -- plug in any OTP provider (SMS pool, virtual number API,
    SMS-forwarding app). Returns None until an OTP arrives."""

    def wait(self, phone: str, timeout: int = 120) -> str | None:
        raise NotImplementedError


class ManualOTP(OTPSink):
    """Reads OTPs from a file that a human / forwarding app appends to."""

    def __init__(self, path: str = "/root/shopee-farm/otp.txt"):
        self.path = path

    def wait(self, phone: str, timeout: int = 120) -> str | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with open(self.path) as f:
                    for line in f:
                        if phone in line and ":" in line:
                            return line.strip().split(":", 1)[1].strip()
            except FileNotFoundError:
                pass
            time.sleep(3)
        return None


class HTTPOTP(OTPSink):
    """Generic HTTP SMS-activation client (adapt to your provider)."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def wait(self, phone: str, timeout: int = 150):
        import requests
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                r = requests.get(
                    f"{self.base_url}/otp",
                    params={"phone": phone, "key": self.api_key},
                    timeout=15,
                )
                code = (r.json() or {}).get("otp")
                if code:
                    return str(code)
            except Exception:
                pass
            time.sleep(5)
        return None
