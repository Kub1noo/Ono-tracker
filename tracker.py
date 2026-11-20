import json
import os
import re
from bs4 import BeautifulSoup
import requests

URL = "http://www.tank-ono.cz/cz/index.php?page=cenik"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
STATE_FILE = "prices.json"


def get_prices():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    }
    response = requests.get(URL, headers=headers, timeout=15)
    if (
        "charset=windows-1250" in response.text.lower()
        or "charset=cp1250" in response.text.lower()
    ):
        response.encoding = "windows-1250"
    else:
        response.encoding = response.apparent_encoding

    soup = BeautifulSoup(response.text, "html.parser")
    prices = {}

    # 1. Prohledáme veškerý čistý text stránky řádek po řádku (funguje pro divy, tabulky i seznamy)
    full_text = soup.get_text("\n", strip=True)
    lines = [line.strip() for line in full_text.split("\n") if line.strip()]

    print("--- DIAGNOSTIKA TEXTU STRÁNKY ---")
    for idx, line in enumerate(lines):
        # Vypíšeme řádky, které obsahují ceny (XX,XX) nebo názvy paliv
        if re.search(
            r"(\d{2}[,\.]\d{2}|Natural|Diesel|Nafta|BA\s*95|N95|AdBlue|LPG)",
            line,
            re.IGNORECASE,
        ):
            print(f"Řádek {idx}: {line}")

    # Spojíme text mezerami pro případ, že název paliva a cena jsou na dvou řádcích pod sebou
    joined_text = " ".join(lines)

    patterns = {
        "Natural 95": (
            r"(?:Natural\s*95|BA\s*95|N\s*95)[^\d]{0,30}(\d{2}[,\.]\d{2})"
        ),
        "Natural 98": (
            r"(?:Natural\s*98|BA\s*98|N\s*98)[^\d]{0,30}(\d{2}[,\.]\d{2})"
        ),
        "Diesel": r"(?:Diesel|Nafta|NM)[^\d]{0,30}(\d{2}[,\.]\d{2})",
    }

    for fuel, pattern in patterns.items():
        match = re.search(pattern, joined_text, re.IGNORECASE)
        if match:
            prices[fuel] = float(match.group(1).replace(",", "."))

    # Pokud se nic nenašlo v textu, vypíšeme iframe nebo obrázky ceníku
    if not prices:
        iframes = [f.get("src") for f in soup.find_all("iframe") if f.get("src")]
        imgs = [
            img.get("src")
            for img in soup.find_all("img")
            if img.get("src") and "cen" in img.get("src").lower()
        ]
        print("Nalezené iframe:", iframes)
        print("Nalezené obrázky ceníku:", imgs)

    return prices


def load_last_prices():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_prices(prices):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(prices, f, indent=2, ensure_ascii=False)


def send_discord_notification(current, previous):
    if not WEBHOOK_URL:
        print("CHYBA: Chybí proměnná DISCORD_WEBHOOK!")
        return

    fields = []
    for fuel in ["Natural 95", "Natural 98", "Diesel"]:
        if fuel in current:
            curr_val = current[fuel]
            prev_val = previous.get(fuel)

            if prev_val is not None and curr_val != prev_val:
                diff = round(curr_val - prev_val, 2)
                sign = "+" if diff > 0 else ""
                arrow = "📈" if diff > 0 else "📉"
                val_str = f"**{curr_val:.2f} Kč** ({arrow} {sign}{diff:.2f} Kč)"
            else:
                val_str = f"**{curr_val:.2f} Kč**"

            fields.append({"name": fuel, "value": val_str, "inline": True})

    embed = {
        "title": "⛽ Tank ONO – Aktuální ceny paliv",
        "url": URL,
        "color": 16750848,
        "fields": fields,
        "footer": {"text": "Zdroj: tank-ono.cz"},
    }

    r = requests.post(WEBHOOK_URL, json={"embeds": [embed]}, timeout=10)
    print(f"Discord odpověď: {r.status_code}")


def main():
    current_prices = get_prices()
    print("Nalezené ceny:", current_prices)

    if not current_prices:
        print("Nepodařilo se načíst žádné ceny z webu.")
        return

    last_prices = load_last_prices()

    if current_prices != last_prices:
        print(f"Změna detekována: {last_prices} -> {current_prices}")
        send_discord_notification(current_prices, last_prices)
        save_prices(current_prices)
    else:
        print("Ceny se nezměnily:", current_prices)


if __name__ == "__main__":
    main()
