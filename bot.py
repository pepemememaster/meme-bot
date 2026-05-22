
import os
import time
import requests
from telegram import Bot

# ===== 基本設定 =====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 模擬設定
TAKE_PROFIT = 1.20
STOP_LOSS = 0.88

TOTAL_PNL = 0
TOTAL_TRADES = 0
WINS = 0
LOSSES = 0
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# ===== 模擬 Token 資料 =====
def get_trending_tokens():
    url = "https://api.dexscreener.com/latest/dex/search?q=solana"

    response = requests.get(url)

    if response.status_code != 200:
        print("Dex API Error")
        return []

    try:
        data = response.json()
    except:
        print("JSON Error")
        return []

    pairs = data.get("pairs", [])

    tokens = []

    for pair in pairs[:10]:
        try:
            token = {
                "name": pair["baseToken"]["name"],
                "symbol": pair["baseToken"]["symbol"],
                "price": float(pair["priceUsd"]),
                "liquidity": float(pair["liquidity"]["usd"]),
                "holders": 500,
                "mint_enabled": False
            }

            tokens.append(token)

        except:
            continue

    return tokens
def send_telegram(msg):
    print(msg)

def is_safe(token):
    if token["liquidity"] < 15000:
        return False

    if token["holders"] < 250:
        return False

    if token["mint_enabled"]:
        return False
    return True
def simulate_trade(token):
    buy_price = token["price"]

    send_telegram(
        f"🚀 Auto Buy\n"
        f"{token['name']} ({token['symbol']})\n"
        f"Buy Price: {buy_price}"
    )

    current_price = buy_price

    for i in range(10):
        time.sleep(3)

        # 模擬價格波動
        current_price *= 1.03

        pnl = (current_price / buy_price - 1) * 100

        print(f"Current Price: {current_price:.6f} | PnL: {pnl:.2f}%")

        if current_price >= buy_price * TAKE_PROFIT:

            global TOTAL_PNL, TOTAL_TRADES, WINS

            TOTAL_PNL += pnl
            TOTAL_TRADES += 1
            WINS += 1

            send_telegram(
                f"✅ Take Profit Hit\n"
                f"{token['symbol']}\n"
                f"PnL: +{pnl:.2f}%"
            )

            print(f"Total PnL: {TOTAL_PNL:.2f}%")
            print(f"Total Trades: {TOTAL_TRADES}")
            print(f"Win Rate: {(WINS / TOTAL_TRADES) * 100:.2f}%")

            return

        if current_price <= buy_price * STOP_LOSS:

            global TOTAL_PNL, TOTAL_TRADES, LOSSES

            TOTAL_PNL += pnl
            TOTAL_TRADES += 1
            LOSSES += 1

            send_telegram(
                f"🛑 Stop Loss Hit\n"
                f"{token['symbol']}\n"
                f"PnL: {pnl:.2f}%"
            )

            print(f"Total PnL: {TOTAL_PNL:.2f}%")
            print(f"Total Trades: {TOTAL_TRADES}")
            print(f"Win Rate: {(WINS / TOTAL_TRADES) * 100:.2f}%")


def main():
    send_telegram("🤖 Meme Bot Started")

    while True:
        for token in get_trending_tokens():
            if is_safe(token):
                simulate_trade(token)

        time.sleep(30)

if __name__ == "__main__":
    main()
