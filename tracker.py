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

    prices = {}
    for row in soup.find_all("tr"):
        cells = [
            c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])
        ]
        # Řádek pobočky začíná např. "ČS Praha - Štěrboholy" nebo "ČS Sokolov" a má 10 sloupců
        if len(cells) >= 6 and cells[0].startswith("ČS"):
            # Sloupce podle obrázků v hlavičce:
            # [1] = n95_c.gif, [2] = n95p_c.gif, [3] = n98_c.gif, [4] = d_c.gif, [5] = d_plus.gif, [6] = ab_c.gif
            mapping = {
                "Natural 95": cells[1],
                "Natural 98": cells[3],
                "Diesel": cells[4],
                "Diesel+": cells[5],
            }
            for fuel, raw_val in mapping.items():
                match = re.search(r"(\d{2}[,\.]\d{2})", raw_val)
                if match:
                    prices[fuel] = float(match.group(1).replace(",", "."))

            if prices:
                break

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
