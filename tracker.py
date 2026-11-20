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
        )
    }
    response = requests.get(URL, headers=headers, timeout=15)
    response.encoding = "windows-1250"
    soup = BeautifulSoup(response.text, "html.parser")

    # Spojíme celý text stránky jedinou mezerou
    text = " ".join(soup.get_text(" ", strip=True).split())

    # Hledáme vzor z ceníku ONO: (N95) (N95+ nebo ---) (N98) (Diesel) (Diesel+ nebo ---)
    # Např.: 36,90 --- 38,90 42,50 42,90
    pattern = (
        r"(\d{2}[,\.]\d{2})\s+(?:\d{2}[,\.]\d{2}|---)\s+(\d{2}[,\.]\d{2}|---)\s+(\d{2}[,\.]\d{2})\s+(\d{2}[,\.]\d{2}|---)"
    )
    match = re.search(pattern, text)

    prices = {}
    if match:
        n95, n98, diesel, diesel_plus = match.groups()
        prices["Natural 95"] = float(n95.replace(",", "."))
        if n98 != "---":
            prices["Natural 98"] = float(n98.replace(",", "."))
        prices["Diesel"] = float(diesel.replace(",", "."))
        if diesel_plus != "---":
            prices["Diesel+"] = float(diesel_plus.replace(",", "."))

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
    for fuel in ["Natural 95", "Natural 98", "Diesel", "Diesel+"]:
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
