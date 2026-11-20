import json
import os
import re
from bs4 import BeautifulSoup
import requests

URL = "https://www.tank-ono.cz/cz/index.php?page=cenik"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
STATE_FILE = "prices.json"


def get_prices():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.8",
    }
    response = requests.get(URL, headers=headers, timeout=15)
    print(f"HTTP Status: {response.status_code}, Délka odpovědi: {len(response.text)} znaků")

    if (
        "charset=windows-1250" in response.text.lower()
        or "charset=cp1250" in response.text.lower()
    ):
        response.encoding = "windows-1250"
    else:
        response.encoding = response.apparent_encoding

    soup = BeautifulSoup(response.text, "html.parser")
    prices = {}

    full_text = soup.get_text("\n", strip=True)
    lines = [line.strip() for line in full_text.split("\n") if line.strip()]
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

    # Pokud se ceny nenašly v textu, vypíšeme všechny obrázky a ukázku textu stránky
    if not prices:
        all_imgs = [img.get("src") for img in soup.find_all("img") if img.get("src")]
        print("Všechny obrázky na stránce:", all_imgs)
        print("Ukázka textu po řádcích (od řádku 40):", lines[40:80])

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
