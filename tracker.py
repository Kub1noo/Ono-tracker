import json
import os
import re
from bs4 import BeautifulSoup
import requests

URL = "http://www.tank-ono.cz/cz/index.php?page=cenik"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
STATE_FILE = "prices.json"


def get_prices():
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(URL, headers=headers, timeout=15)
    response.encoding = "windows-1250"
    soup = BeautifulSoup(response.text, "html.parser")

    prices = {}
    for row in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        row_text = " ".join(cells)

        for fuel in ["Natural 95", "Natural 98", "Diesel"]:
            if fuel in row_text and fuel not in prices:
                # Najde cenu ve formátu XX,XX nebo XX.XX (např. 34,90)
                match = re.search(r"(\d{2}[,\.]\d{2})", row_text)
                if match:
                    prices[fuel] = float(match.group(1).replace(",", "."))
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
        print("Chybí DISCORD_WEBHOOK!")
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
        "title": "⛽ Tank ONO – Změna cen paliv",
        "url": URL,
        "color": 16750848,  # Oranžová
        "fields": fields,
        "footer": {"text": "Zdroj: tank-ono.cz"},
    }

    requests.post(WEBHOOK_URL, json={"embeds": [embed]}, timeout=10)


def main():
    current_prices = get_prices()
    if not current_prices:
        print("Nepodařilo se načíst ceny z webu.")
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
