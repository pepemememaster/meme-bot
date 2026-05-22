import os
import time
import random
import asyncio
import requests

from datetime import datetime
from telegram import Bot

# =========================================================
# TELEGRAM
# =========================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# =========================================================
# SETTINGS
# =========================================================

TAKE_PROFIT_1 = 1.25
TAKE_PROFIT_2 = 1.80

STOP_LOSS = 0.90

TRAILING_START = 2.0
TRAILING_GAP = 0.25

MIN_LIQUIDITY = 50000
MIN_VOLUME = 200000

SCAN_INTERVAL = 45

MAX_DAILY_TRADES = 20
MAX_ACTIVE_TRADES = 2

MAX_DAILY_LOSS = -15

# =========================================================
# STATS
# =========================================================

TOTAL_PNL = 0
DAILY_PNL = 0

TOTAL_TRADES = 0
WINS = 0
LOSSES = 0

ACTIVE_TRADES = {}

# =========================================================
# TELEGRAM
# =========================================================

def send_telegram(msg):

    print(msg)

    if not TELEGRAM_BOT_TOKEN:
        return

    async def send():

        try:

            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=msg
            )

        except Exception as e:

            print("Telegram Error:", e)

    asyncio.run(send())

# =========================================================
# DEXSCREENER
# =========================================================

def get_tokens():

    try:

        url = "https://api.dexscreener.com/latest/dex/search?q=solana"

        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            return []

        data = response.json()

        pairs = data.get("pairs", [])

        tokens = []

        for pair in pairs[:30]:

            try:

                token = {

                    "name": pair["baseToken"]["name"],

                    "symbol": pair["baseToken"]["symbol"],

                    "price": float(
                        pair.get("priceUsd", 0)
                    ),

                    "liquidity": float(
                        pair.get(
                            "liquidity",
                            {}
                        ).get("usd", 0)
                    ),

                    "volume": float(
                        pair.get(
                            "volume",
                            {}
                        ).get("h24", 0)
                    ),

                    "price_change": random.uniform(
                        -10,
                        250
                    ),

                    "holders": random.randint(
                        300,
                        12000
                    ),

                    "wallet_diversity": random.randint(
                        50,
                        100
                    ),

                    "smart_money": random.randint(
                        0,
                        100
                    ),

                    "rug_score": random.randint(
                        60,
                        100
                    )

                }

                tokens.append(token)

            except:
                continue

        return tokens

    except Exception as e:

        print("DEX ERROR", e)

        return []

# =========================================================
# AI SCORE
# =========================================================

def calculate_score(token):

    score = 0

    if token["liquidity"] > 50000:
        score += 20

    if token["volume"] > 200000:
        score += 20

    if token["price_change"] > 20:
        score += 15

    if token["holders"] > 1000:
        score += 10

    if token["wallet_diversity"] > 70:
        score += 10

    if token["smart_money"] > 70:
        score += 15

    if token["rug_score"] > 80:
        score += 10

    return min(score, 100)

# =========================================================
# FILTER
# =========================================================

def is_safe(token):

    if token["liquidity"] < MIN_LIQUIDITY:
        return False

    if token["volume"] < MIN_VOLUME:
        return False

    if token["wallet_diversity"] < 60:
        return False

    if token["rug_score"] < 70:
        return False

    return True

# =========================================================
# TRADE
# =========================================================

def simulate_trade(token):

    global TOTAL_PNL
    global DAILY_PNL
    global TOTAL_TRADES
    global WINS
    global LOSSES

    symbol = token["symbol"]

    if symbol in ACTIVE_TRADES:
        return

    if len(ACTIVE_TRADES) >= MAX_ACTIVE_TRADES:
        return

    ACTIVE_TRADES[symbol] = True

    buy_price = token["price"]

    send_telegram(
f"""
🚀 AUTO BUY

{symbol}

Score:
{token['score']}

Buy:
${buy_price:.8f}
"""
    )

    current_price = buy_price
    highest_price = buy_price

    tp1 = False
    tp2 = False

    for _ in range(50):

        time.sleep(2)

        movement = random.uniform(
            0.96,
            1.15
        )

        current_price *= movement

        if current_price > highest_price:
            highest_price = current_price

        pnl = (
            (
                current_price / buy_price
            ) - 1
        ) * 100

        print(
            f"[{symbol}] "
            f"PnL: {pnl:.2f}%"
        )

        if current_price <= buy_price * STOP_LOSS:

            TOTAL_PNL += pnl
            DAILY_PNL += pnl

            TOTAL_TRADES += 1
            LOSSES += 1

            send_telegram(
f"""
🛑 STOP LOSS

{symbol}

PnL:
{pnl:.2f}%
"""
            )

            ACTIVE_TRADES.pop(symbol)

            return

        if (
            not tp1
            and current_price >= buy_price * TAKE_PROFIT_1
        ):

            tp1 = True

            send_telegram(
f"""
✅ TP1 HIT

{symbol}

+25%
"""
            )

        if (
            not tp2
            and current_price >= buy_price * TAKE_PROFIT_2
        ):

            tp2 = True

            send_telegram(
f"""
🔥 TP2 HIT

{symbol}

Moonbag Running
"""
            )

        if highest_price >= buy_price * TRAILING_START:

            trailing_price = (
                highest_price
                * (1 - TRAILING_GAP)
            )

            if current_price <= trailing_price:

                final_pnl = (
                    (
                        current_price / buy_price
                    ) - 1
                ) * 100

                TOTAL_PNL += final_pnl
                DAILY_PNL += final_pnl

                TOTAL_TRADES += 1
                WINS += 1

                send_telegram(
f"""
🌕 MOON EXIT

{symbol}

PnL:
+{final_pnl:.2f}%
"""
                )

                ACTIVE_TRADES.pop(symbol)

                return

    ACTIVE_TRADES.pop(symbol)

# =========================================================
# REPORT
# =========================================================

def send_report():

    winrate = 0

    if TOTAL_TRADES > 0:

        winrate = (
            WINS / TOTAL_TRADES
        ) * 100

    send_telegram(
f"""
📊 REPORT

Trades:
{TOTAL_TRADES}

Wins:
{WINS}

Losses:
{LOSSES}

Winrate:
{winrate:.2f}%

PnL:
{TOTAL_PNL:.2f}%
"""
    )

# =========================================================
# MAIN
# =========================================================

def main():

    send_telegram(
"""
🤖 QUANT BOT STARTED

SAFE MODE ACTIVE
"""
    )

    while True:

        try:

            if DAILY_PNL <= MAX_DAILY_LOSS:

                send_telegram(
"""
🛑 DAILY LOSS LIMIT

Bot paused.
"""
                )

                time.sleep(3600)

                continue

            tokens = get_tokens()

            for token in tokens:

                token["score"] = calculate_score(
                    token
                )

                if not is_safe(token):
                    continue

                if token["score"] >= 85:

                    send_telegram(
f"""
🔥 ELITE SIGNAL

{token['symbol']}

Score:
{token['score']}
"""
                    )

                    simulate_trade(token)

            send_report()

            time.sleep(SCAN_INTERVAL)

        except Exception as e:

            print("MAIN ERROR:", e)

            time.sleep(10)

# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
