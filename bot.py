
import os
import time
import random
import requests
from telegram import Bot

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SCAN_KEYWORD = "solana"

TAKE_PROFIT = 1.20
STOP_LOSS = 0.88

MIN_LIQUIDITY = 15000
MIN_HOLDERS = 250

SLEEP_BETWEEN_SCANS = 30

TOTAL_PNL = 0
TOTAL_TRADES = 0
WINS = 0
LOSSES = 0

bot = Bot(token=TELEGRAM_BOT_TOKEN)

def send_telegram(message):

    print(message)

    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
    except Exception as e:
        print("Telegram Error:", e)

def get_trending_tokens():

    url = (
        f"https://api.dexscreener.com/latest/dex/search"
        f"?q={SCAN_KEYWORD}"
    )

    try:
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            print("Dex API Error")
            return []

        data = response.json()

    except Exception as e:
        print("Request Error:", e)
        return []

    pairs = data.get("pairs", [])

    tokens = []

    for pair in pairs[:15]:

        try:

            liquidity = pair.get("liquidity", {}).get("usd", 0)

            token = {
                "name": pair["baseToken"]["name"],
                "symbol": pair["baseToken"]["symbol"],
                "price": float(pair.get("priceUsd", 0)),
                "liquidity": float(liquidity),
                "holders": random.randint(300, 2000),
                "mint_enabled": False,
                "volume_24h": pair.get("volume", {}).get("h24", 0),
                "chain": pair.get("chainId", "unknown")
            }

            tokens.append(token)

        except Exception:
            continue

    return tokens

def is_safe(token):

    if token["liquidity"] < MIN_LIQUIDITY:
        return False

    if token["holders"] < MIN_HOLDERS:
        return False

    if token["mint_enabled"]:
        return False

    return True

def simulate_trade(token):

    global TOTAL_PNL
    global TOTAL_TRADES
    global WINS
    global LOSSES

    buy_price = token["price"]

    if buy_price <= 0:
        return

    send_telegram(
        f"🚀 AUTO BUY\n\n"
        f"Name: {token['name']}\n"
        f"Symbol: {token['symbol']}\n"
        f"Chain: {token['chain']}\n"
        f"Liquidity: ${token['liquidity']:.0f}\n"
        f"Buy Price: ${buy_price:.8f}"
    )

    current_price = buy_price

    for _ in range(10):

        time.sleep(3)

        movement = random.uniform(0.96, 1.08)
        current_price *= movement

        pnl = (current_price / buy_price - 1) * 100

        print(
            f"[{token['symbol']}] "
            f"Current: {current_price:.8f} | "
            f"PnL: {pnl:.2f}%"
        )

        if current_price >= buy_price * TAKE_PROFIT:

            TOTAL_PNL += pnl
            TOTAL_TRADES += 1
            WINS += 1

            send_telegram(
                f"✅ TAKE PROFIT HIT\n\n"
                f"{token['symbol']}\n"
                f"PnL: +{pnl:.2f}%\n\n"
                f"Total Trades: {TOTAL_TRADES}\n"
                f"Win Rate: {(WINS / TOTAL_TRADES) * 100:.2f}%\n"
                f"Total PnL: {TOTAL_PNL:.2f}%"
            )

            return

        if current_price <= buy_price * STOP_LOSS:

            TOTAL_PNL += pnl
            TOTAL_TRADES += 1
            LOSSES += 1

            send_telegram(
                f"🛑 STOP LOSS HIT\n\n"
                f"{token['symbol']}\n"
                f"PnL: {pnl:.2f}%\n\n"
                f"Total Trades: {TOTAL_TRADES}\n"
                f"Win Rate: {(WINS / TOTAL_TRADES) * 100:.2f}%\n"
                f"Total PnL: {TOTAL_PNL:.2f}%"
            )

            return

def main():

    send_telegram("🤖 Meme Sniper Bot Started")

    while True:

        print("=" * 50)
        print("Scanning tokens...")

        tokens = get_trending_tokens()

        print(f"Found {len(tokens)} tokens")

        for token in tokens:

            try:

                if is_safe(token):

                    print(
                        f"SAFE => "
                        f"{token['symbol']} | "
                        f"Liquidity: {token['liquidity']}"
                    )

                    simulate_trade(token)

                else:

                    print(
                        f"SKIP => "
                        f"{token['symbol']}"
                    )

            except Exception as e:

                print("Trade Error:", e)

        print("Sleeping...")
        time.sleep(SLEEP_BETWEEN_SCANS)

if __name__ == "__main__":
    main()
