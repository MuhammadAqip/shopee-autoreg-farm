"""Credential + identity generation for Shopee accounts (Indonesian market)."""
import random
import string

FIRST_M = ["Andi", "Budi", "Dewa", "Eka", "Fajar", "Gunawan", "Hendra", "Irfan",
           "Joko", "Krisna", "Lukman", "Maulana", "Naufal", "Oscar", "Putra",
           "Rizky", "Sandi", "Teguh", "Umar", "Wahyu", "Yanto", "Zaki"]
FIRST_F = ["Ayu", "Bella", "Citra", "Diana", "Elsa", "Fitri", "Gita", "Hana",
           "Indah", "Julia", "Kartika", "Lina", "Maya", "Nadia", "Olivia",
           "Putri", "Ratna", "Sinta", "Tiara", "Ulfa", "Wulan", "Zahra"]
LAST = ["Pratama", "Kusuma", "Wijaya", "Santoso", "Permana", "Saputra",
        "Nugroho", "Hidayat", "Ramadhan", "Firmansyah", "Setiawan", "Utami",
        "Anggraini", "Lestari", "Maulida", "Handayani"]

PHONE_PREFIX = ["0812", "0813", "0821", "0822", "0823", "0851", "0852", "0853",
                "0855", "0856", "0857", "0858", "0895", "0896", "0897", "0898", "0899"]


class AccountGen:
    def __init__(self):
        self.gender = random.choice(["M", "F"])

    def name(self) -> str:
        first = random.choice(FIRST_M if self.gender == "M" else FIRST_F)
        return f"{first} {random.choice(LAST)}"

    def username(self) -> str:
        base = random.choice(FIRST_M + FIRST_F).lower()
        return f"{base}{''.join(random.choices(string.digits, k=random.randint(2, 4)))}"

    def password(self) -> str:
        letters = string.ascii_letters
        digits = string.digits
        special = "!@#$%"
        core = (
            "".join(random.choices(letters, k=8))
            + "".join(random.choices(digits, k=4))
            + random.choice(special)
        )
        return core

    def phone(self) -> str:
        return random.choice(PHONE_PREFIX) + "".join(random.choices(string.digits, k=8))

    def email(self, domain: str = None) -> str:
        local = (
            "".join(random.choices(string.ascii_lowercase, k=random.randint(6, 10)))
            + "".join(random.choices(string.digits, k=random.randint(2, 4)))
        )
        dom = domain or random.choice(["gmail.com", "yahoo.com", "outlook.com"])
        return f"{local}@{dom}"

    def birthdate(self) -> str:
        return f"{random.randint(1, 28):02d}/{random.randint(1, 12):02d}/{random.randint(1985, 2004)}"

    def profile(self, email_domain: str = None) -> dict:
        return {
            "name": self.name(),
            "username": self.username(),
            "password": self.password(),
            "phone": self.phone(),
            "email": self.email(email_domain),
            "gender": "male" if self.gender == "M" else "female",
            "birthdate": self.birthdate(),
        }
