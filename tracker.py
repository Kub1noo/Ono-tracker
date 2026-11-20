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

    # Vytáhneme čisté položky textu tak, jak jdou za sebou na stránce
    lines = [
        line.strip()
        for line in soup.get_text("\n", strip=True).split("\n")
        if line.strip()
    ]

    prices = {}
    for i, item in enumerate(lines):
        # Najdeme řádek s pražskou pobočkou (Štěrboholy / Dolní Měcholupy) nebo jakoukoli ČS
        if ("Štěrboholy" in item or "Měcholupy" in item) and i + 5 < len(lines):
            # Za názvem pobočky následuje v pevném pořadí:
            # +1: Natural 95, +2: Natural 95+, +3: Natural 98, +4: Diesel, +5: Diesel+
            candidates = {
                "Natural 95": lines[i + 1],
                "Natural 98": lines[i + 3],
                "Diesel": lines[i + 4],
                "Diesel+": lines[i + 5],
            }
            for fuel, val in candidates.items():
                match = re.search(r"(\d{2}[,\.]\d{2})", val)
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
        "footer": {"text": "Zdroj: tank-ono.cz (Praha)"},
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
