
import os
import time
import random
import asyncio
import requests

from telegram import Bot

# =========================
# Telegram 設定
# =========================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# =========================
# 模擬設定
# =========================

TAKE_PROFIT = 1.20
STOP_LOSS = 0.88

TOTAL_PNL = 0
TOTAL_TRADES = 0
WINS = 0
LOSSES = 0

# =========================
# Telegram 發送
# =========================

def send_telegram(msg):

    print(msg)

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:

        async def send():

            try:

                await bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=msg
                )

            except Exception as e:
                print("Telegram Error:", e)

        asyncio.run(send())

# =========================
# Dex API
# =========================

def get_trending_tokens():

    try:

        url = "https://api.dexscreener.com/latest/dex/search?q=solana"

        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            print("Dex API Error")
            return []

        data = response.json()

        pairs = data.get("pairs", [])

        tokens = []

        for pair in pairs[:10]:

            try:

                liquidity = float(
                    pair.get("liquidity", {}).get("usd", 0)
                )

                volume = float(
                    pair.get("volume", {}).get("h24", 0)
                )

                token = {

                    "name": pair["baseToken"]["name"],
                    "symbol": pair["baseToken"]["symbol"],
                    "price": float(pair["priceUsd"]),
                    "liquidity": liquidity,
                    "volume": volume,
                    "chain": pair.get("chainId", "unknown"),
                    "mint_enabled": False,
                    "holders": random.randint(200, 5000)

                }

                tokens.append(token)

            except:
                continue

        return tokens

    except Exception as e:

        print("Dex Error:", e)

        return []

# =========================
# 安全檢查
# =========================

def is_safe(token):

    if token["liquidity"] < 15000:
        return False

    if token["volume"] < 50000:
        return False

    if token["holders"] < 250:
        return False

    if token["mint_enabled"]:
        return False

    return True

# =========================
# 模擬交易
# =========================

def simulate_trade(token):

    global TOTAL_PNL
    global TOTAL_TRADES
    global WINS
    global LOSSES

    buy_price = token["price"]

    send_telegram(
        f"""
🚀 AUTO BUY

Name: {token['name']}
Symbol: {token['symbol']}
Chain: {token['chain']}

Liquidity: ${token['liquidity']:.0f}
24h Volume: ${token['volume']:.0f}

Buy Price: ${buy_price:.8f}
"""
    )

    current_price = buy_price

    for i in range(20):

        time.sleep(2)

        movement = random.uniform(0.92, 1.12)

        current_price *= movement

        pnl = ((current_price / buy_price) - 1) * 100

        print(
            f"[{token['symbol']}] Current: {current_price:.8f} | PnL: {pnl:.2f}%"
        )

        # TAKE PROFIT

        if current_price >= buy_price * TAKE_PROFIT:

            TOTAL_PNL += pnl
            TOTAL_TRADES += 1
            WINS += 1

            send_telegram(
                f"""
✅ TAKE PROFIT HIT

{token['symbol']}

PnL: +{pnl:.2f}%

Total Trades: {TOTAL_TRADES}
Wins: {WINS}
Losses: {LOSSES}

Win Rate: {(WINS / TOTAL_TRADES) * 100:.2f}%
Total PnL: {TOTAL_PNL:.2f}%
"""
            )

            return

        # STOP LOSS

        if current_price <= buy_price * STOP_LOSS:

            TOTAL_PNL += pnl
            TOTAL_TRADES += 1
            LOSSES += 1

            send_telegram(
                f"""
🛑 STOP LOSS HIT

{token['symbol']}

PnL: {pnl:.2f}%

Total Trades: {TOTAL_TRADES}
Wins: {WINS}
Losses: {LOSSES}

Win Rate: {(WINS / TOTAL_TRADES) * 100:.2f}%
Total PnL: {TOTAL_PNL:.2f}%
"""
            )

            return

# =========================
# 主程式
# =========================

def main():

    send_telegram("🧪 TEST MESSAGE")
    send_telegram("🤖 Meme Sniper Bot Started")

    while True:

        try:

            tokens = get_trending_tokens()

            print(f"Found {len(tokens)} tokens")

            for token in tokens:

                print(
                    f"Checking {token['symbol']} | Liquidity ${token['liquidity']:.0f}"
                )

                if is_safe(token):

                    print(
                        f"SAFE => {token['symbol']} | Liquidity ${token['liquidity']:.0f}"
                    )

                    simulate_trade(token)

                else:

                    print(
                        f"SKIP => {token['symbol']}"
                    )

            time.sleep(30)

        except Exception as e:

            print("MAIN ERROR:", e)

            time.sleep(10)

# =========================
# 啟動
# =========================

if __name__ == "__main__":
    main()
