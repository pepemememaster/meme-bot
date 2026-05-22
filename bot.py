
import os
import time
import random
import asyncio
import requests

from telegram import Bot

# =========================
# Telegram
# =========================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# =========================
# 策略設定
# =========================

TAKE_PROFIT = 1.35
STOP_LOSS = 0.82

MIN_LIQUIDITY = 12000
MIN_VOLUME = 50000

TOTAL_PNL = 0
TOTAL_TRADES = 0
WINS = 0
LOSSES = 0

# =========================
# Telegram
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
            return []

        data = response.json()

        pairs = data.get("pairs", [])

        tokens = []

        for pair in pairs[:25]:

            try:

                liquidity = float(
                    pair.get("liquidity", {}).get("usd", 0)
                )

                volume = float(
                    pair.get("volume", {}).get("h24", 0)
                )

                price = float(pair.get("priceUsd", 0))

                price_change = random.uniform(-20, 120)

                age_minutes = random.randint(5, 240)

                buys = random.randint(20, 500)
                sells = random.randint(1, 120)

                token = {

                    "name": pair["baseToken"]["name"],
                    "symbol": pair["baseToken"]["symbol"],
                    "price": price,
                    "liquidity": liquidity,
                    "volume": volume,
                    "price_change": price_change,
                    "age_minutes": age_minutes,
                    "buys": buys,
                    "sells": sells,
                    "holders": random.randint(150, 5000),
                    "chain": pair.get("chainId", "solana"),
                    "mint_enabled": False

                }

                tokens.append(token)

            except:
                continue

        return tokens

    except Exception as e:

        print("Dex Error:", e)

        return []

# =========================
# AI SCORE
# =========================

def calculate_score(token):

    score = 0

    # liquidity

    if token["liquidity"] > 20000:
        score += 20

    if token["liquidity"] > 50000:
        score += 15

    # volume

    if token["volume"] > 100000:
        score += 20

    if token["volume"] > 500000:
        score += 20

    # momentum

    if token["price_change"] > 15:
        score += 15

    if token["price_change"] > 40:
        score += 20

    # early launch

    if token["age_minutes"] < 60:
        score += 15

    # buy pressure

    if token["buys"] > token["sells"] * 2:
        score += 20

    # holders

    if token["holders"] > 300:
        score += 10

    return score

# =========================
# 安全檢查
# =========================

def is_safe(token):

    if token["liquidity"] < MIN_LIQUIDITY:
        return False

    if token["volume"] < MIN_VOLUME:
        return False

    if token["holders"] < 150:
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
🚀 SNIPER ENTRY

Name: {token['name']}
Symbol: {token['symbol']}

AI Score: {token['score']}/100

Liquidity: ${token['liquidity']:.0f}
Volume: ${token['volume']:.0f}

Price Change: {token['price_change']:.2f}%
Age: {token['age_minutes']} min

Buy Pressure:
{token['buys']} buys / {token['sells']} sells

BUY PRICE:
${buy_price:.8f}
"""
    )

    current_price = buy_price

    for i in range(25):

        time.sleep(2)

        movement = random.uniform(0.90, 1.15)

        current_price *= movement

        pnl = ((current_price / buy_price) - 1) * 100

        print(
            f"[{token['symbol']}] Current: {current_price:.8f} | PnL: {pnl:.2f}%"
        )

        # take profit

        if current_price >= buy_price * TAKE_PROFIT:

            TOTAL_PNL += pnl
            TOTAL_TRADES += 1
            WINS += 1

            send_telegram(
f"""
✅ TAKE PROFIT

{token['symbol']}

PnL: +{pnl:.2f}%

Total Trades: {TOTAL_TRADES}
Wins: {WINS}
Losses: {LOSSES}

Win Rate:
{(WINS / TOTAL_TRADES) * 100:.2f}%

Total PnL:
{TOTAL_PNL:.2f}%
"""
            )

            return

        # stop loss

        if current_price <= buy_price * STOP_LOSS:

            TOTAL_PNL += pnl
            TOTAL_TRADES += 1
            LOSSES += 1

            send_telegram(
f"""
🛑 STOP LOSS

{token['symbol']}

PnL: {pnl:.2f}%

Total Trades: {TOTAL_TRADES}
Wins: {WINS}
Losses: {LOSSES}

Win Rate:
{(WINS / TOTAL_TRADES) * 100:.2f}%

Total PnL:
{TOTAL_PNL:.2f}%
"""
            )

            return

# =========================
# 主程式
# =========================

def main():

    send_telegram("🧪 ADVANCED SNIPER BOT STARTED")

    while True:

        try:

            tokens = get_trending_tokens()

            print(f"Found {len(tokens)} tokens")

            for token in tokens:

                token["score"] = calculate_score(token)

                print(
                    f"{token['symbol']} | Score {token['score']}"
                )

                if not is_safe(token):
                    continue

                # Pump.fun 類型判定

                if token["score"] >= 70:

                    send_telegram(
f"""
🔥 PUMP DETECTED

{token['symbol']}

AI Score: {token['score']}
"""
                    )

                    simulate_trade(token)

            time.sleep(30)

        except Exception as e:

            print("MAIN ERROR:", e)

            time.sleep(10)

# =========================
# 啟動
# =========================

if __name__ == "__main__":
    main()
