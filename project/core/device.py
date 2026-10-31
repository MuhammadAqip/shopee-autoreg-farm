"""Device fingerprint spoofing for Shopee registration.
Shopee binds accounts to device identity server-side; a fresh, plausible
fingerprint per account is the core anti-duplicate primitive."""
import random
import uuid
import hashlib


BRANDS = {
    "Samsung": ["SM-A525F", "SM-A325F", "SM-A125F", "SM-G991B", "SM-M325F", "SM-A135F"],
    "Xiaomi": ["M2101K7AG", "2201117TG", "M2007J20CG", "2201123G", "220333QAG"],
    "Oppo": ["CPH2211", "CPH2239", "CPH2185", "CPH2273", "CPH2363"],
    "Vivo": ["V2027", "V2109", "V2111", "V2045", "V2146"],
    "Realme": ["RMX3263", "RMX3231", "RMX2193", "RMX3151", "RMX3501"],
    "Infinix": ["X6819", "X682B", "X663B", "X6817", "X6816"],
}
ANDROID_VERSIONS = ["11", "12", "13", "14"]
DPI = [240, 320, 420, 440, 480]
SCREENS = [
    (720, 1600), (1080, 2340), (1080, 2400),
    (720, 1560), (1080, 1920), (1440, 3200),
]


def _hex(n: int) -> str:
    return "".join(random.choices("0123456789abcdef", k=n))


def luhn_imei() -> str:
    """Luhn-valid 15-digit IMEI (passes the checksum many SDKs run)."""
    body = [random.randint(0, 9) for _ in range(14)]
    total = 0
    for i, d in enumerate(body):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    check = (10 - (total % 10)) % 10
    return "".join(map(str, body)) + str(check)


class Device:
    """One spoofed Android device profile."""

    def __init__(self):
        self.brand = random.choice(list(BRANDS))
        self.model = random.choice(BRANDS[self.brand])
        self.android_version = random.choice(ANDROID_VERSIONS)
        self.android_id = _hex(16)
        self.imei = luhn_imei()
        self.advertising_id = str(uuid.uuid4())
        self.mac = self._mac()
        self.dpi = random.choice(DPI)
        self.screen_w, self.screen_h = random.choice(SCREENS)
        self.build_fingerprint = (
            f"{self.brand.lower()}/{self.model}/{self.model}:"
            f"{self.android_version}/RP1A.201005.001/{_hex(8)}:user/release-keys"
        )

    @staticmethod
    def _mac() -> str:
        oui = random.choice([
            [0x00, 0x1A, 0x11], [0x3C, 0x5A, 0xB4],
            [0xAC, 0xC1, 0xEE], [0xE8, 0xBB, 0xA8],
        ])
        tail = [random.randint(0x00, 0xFF) for _ in range(3)]
        return ":".join(f"{b:02X}" for b in oui + tail)

    @property
    def shopee_device_id(self) -> str:
        """Shopee's x-sap-ri / SPC_F device cookie value seed."""
        raw = f"{self.imei}{self.android_id}{self.advertising_id}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def user_agent(self) -> str:
        return (
            f"Shopee {self._app_ver()} (Android {self.android_version}; "
            f"{self.brand} {self.model} Build/RP1A.201005.001; "
            f"{self.screen_w}x{self.screen_h})"
        )

    @staticmethod
    def _app_ver() -> str:
        return random.choice(["3.12.15", "3.14.20", "3.16.10", "3.18.25", "3.20.11"])

    def screen_attrs(self) -> dict:
        return {
            "screen_width": self.screen_w,
            "screen_height": self.screen_h,
            "density_dpi": self.dpi,
            "density": round(self.dpi / 160, 2),
        }

    def as_dict(self) -> dict:
        return {
            "brand": self.brand,
            "model": self.model,
            "android_version": self.android_version,
            "android_id": self.android_id,
            "imei": self.imei,
            "advertising_id": self.advertising_id,
            "mac": self.mac,
            "fingerprint": self.build_fingerprint,
            "spc_device_id": self.shopee_device_id,
            "user_agent": self.user_agent(),
            **self.screen_attrs(),
        }
