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
    if (
        "charset=windows-1250" in response.text.lower()
        or "charset=cp1250" in response.text.lower()
    ):
        response.encoding = "windows-1250"
    else:
        response.encoding = response.apparent_encoding

    soup = BeautifulSoup(response.text, "html.parser")
    prices = {}

    print("--- DIAGNOSTIKA CENÍKU (od řádku 25) ---")
    for i, row in enumerate(soup.find_all("tr")):
        cells = [
            c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])
        ]
        if not any(cells):
            continue

        if i >= 25:
            print(f"Řádek {i}: {cells}")

        row_text = " ".join(cells)

        if (
            any(
                k in row_text
                for k in ["Natural 95", "BA 95", "N95", "Natural95"]
            )
            and "Natural 95" not in prices
        ):
            match = re.search(r"(\d{2}[,\.]\d{2})", row_text)
            if match:
                prices["Natural 95"] = float(match.group(1).replace(",", "."))
        if (
            any(
                k in row_text
                for k in ["Natural 98", "BA 98", "N98", "Natural98"]
            )
            and "Natural 98" not in prices
        ):
            match = re.search(r"(\d{2}[,\.]\d{2})", row_text)
            if match:
                prices["Natural 98"] = float(match.group(1).replace(",", "."))
        if (
            any(k in row_text for k in ["Diesel", "Nafta", "NM"])
            and "Diesel" not in prices
        ):
            match = re.search(r"(\d{2}[,\.]\d{2})", row_text)
            if match:
                prices["Diesel"] = float(match.group(1).replace(",", "."))

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
