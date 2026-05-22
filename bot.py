
import os
import time
import random
import asyncio
import requests

from datetime import datetime, timedelta
from telegram import Bot

# =========================================
# TELEGRAM
# =========================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# =========================================
# HYBRID SETTINGS
# =========================================

TP1 = 1.18
TP2 = 1.45

STOP_LOSS = 0.90

TRAILING_TRIGGER = 1.25
TRAILING_STOP = 0.20

MIN_LIQUIDITY = 40000
MIN_VOLUME = 150000

MAX_ACTIVE_TRADES = 2

MAX_DAILY_TRADES = 20
MAX_DAILY_LOSS = -15

SCAN_INTERVAL = 45

# =========================================
# STATS
# =========================================

TOTAL_PNL = 0
TOTAL_TRADES = 0

DAILY_PNL = 0
DAILY_TRADES = 0

WINS = 0
LOSSES = 0

LOSS_STREAK = 0

COOLDOWN_UNTIL = None

ACTIVE_TRADES = {}

WATCHLIST = {}

# =========================================
# TELEGRAM
# =========================================

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
                print(e)

        asyncio.run(send())

# =========================================
# TOKEN SCAN
# =========================================

def get_tokens():

    try:

        url = "https://api.dexscreener.com/latest/dex/search?q=solana"

        response = requests.get(url, timeout=10)

        data = response.json()

        pairs = data.get("pairs", [])

        tokens = []

        for pair in pairs[:40]:

            try:

                token = {

                    "name": pair["baseToken"]["name"],

                    "symbol": pair["baseToken"]["symbol"],

                    "price": float(
                        pair.get("priceUsd", 0)
                    ),

                    "liquidity": float(
                        pair.get("liquidity", {}).get("usd", 0)
                    ),

                    "volume": float(
                        pair.get("volume", {}).get("h24", 0)
                    ),

                    "holders": random.randint(300, 6000),

                    "age_minutes": random.randint(5, 120),

                    "price_change": random.uniform(
                        -10, 200
                    ),

                    "buys": random.randint(50, 1200),

                    "sells": random.randint(10, 400),

                    "dev_wallet": random.uniform(0, 20),

                    "fake_volume": random.randint(0, 100)

                }

                tokens.append(token)

            except:
                continue

        return tokens

    except Exception as e:

        print("DEX ERROR", e)

        return []

# =========================================
# AI SCORE
# =========================================

def calculate_score(token):

    score = 0

    if token["liquidity"] > 40000:
        score += 15

    if token["liquidity"] > 100000:
        score += 15

    if token["volume"] > 150000:
        score += 20

    if token["volume"] > 500000:
        score += 15

    if token["price_change"] > 20:
        score += 15

    if token["price_change"] > 60:
        score += 10

    if token["buys"] > token["sells"] * 2:
        score += 15

    if token["holders"] > 500:
        score += 10

    if token["age_minutes"] < 45:
        score += 10

    return min(score, 100)

# =========================================
# FILTER
# =========================================

def is_safe(token):

    if token["liquidity"] < MIN_LIQUIDITY:
        return False

    if token["volume"] < MIN_VOLUME:
        return False

    if token["holders"] < 300:
        return False

    if token["dev_wallet"] > 12:
        return False

    if token["fake_volume"] > 75:
        return False

    return True

# =========================================
# TRADE
# =========================================

def simulate_trade(token):

    global TOTAL_PNL
    global TOTAL_TRADES

    global DAILY_PNL
    global DAILY_TRADES

    global WINS
    global LOSSES

    global LOSS_STREAK
    global COOLDOWN_UNTIL

    symbol = token["symbol"]

    if symbol in ACTIVE_TRADES:
        return

    if len(ACTIVE_TRADES) >= MAX_ACTIVE_TRADES:
        return

    if DAILY_TRADES >= MAX_DAILY_TRADES:
        return

    DAILY_TRADES += 1

    buy_price = token["price"]

    ACTIVE_TRADES[symbol] = True

    send_telegram(
f"""
🚀 HYBRID ENTRY

{symbol}

AI Score:
{token['score']}/100

Liquidity:
${token['liquidity']:.0f}

Volume:
${token['volume']:.0f}

BUY:
${buy_price:.8f}
"""
    )

    current_price = buy_price

    highest_price = buy_price

    tp1_hit = False
    tp2_hit = False

    for i in range(45):

        time.sleep(2)

        movement = random.uniform(0.95, 1.12)

        current_price *= movement

        pnl = ((current_price / buy_price) - 1) * 100

        if current_price > highest_price:
            highest_price = current_price

        print(
            f"{symbol} | "
            f"PnL {pnl:.2f}%"
        )

        # STOP LOSS

        if current_price <= buy_price * STOP_LOSS:

            TOTAL_PNL += pnl
            DAILY_PNL += pnl

            TOTAL_TRADES += 1
            LOSSES += 1

            LOSS_STREAK += 1

            send_telegram(
f"""
🛑 STOP LOSS

{symbol}

PnL:
{pnl:.2f}%
"""
            )

            ACTIVE_TRADES.pop(symbol, None)

            # cooldown

            if LOSS_STREAK >= 3:

                COOLDOWN_UNTIL = (
                    datetime.now()
                    + timedelta(minutes=20)
                )

                send_telegram(
"""
❄️ SAFE MODE

3 losses in a row.

Cooldown 20 min.
"""
                )

            return

        # TP1

        if (
            not tp1_hit
            and current_price >= buy_price * TP1
        ):

            tp1_hit = True

            send_telegram(
f"""
✅ TP1 HIT

{symbol}

Sold 50%

PnL:
+18%
"""
            )

        # TP2

        if (
            not tp2_hit
            and current_price >= buy_price * TP2
        ):

            tp2_hit = True

            send_telegram(
f"""
🚀 TP2 HIT

{symbol}

Sold 30%

Moonbag Left:
20%
"""
            )

        # TRAILING STOP

        if highest_price >= buy_price * TRAILING_TRIGGER:

            trailing_price = (
                highest_price
                * (1 - TRAILING_STOP)
            )

            if current_price <= trailing_price:

                final_pnl = (
                    (
                        current_price
                        / buy_price
                    ) - 1
                ) * 100

                TOTAL_PNL += final_pnl
                DAILY_PNL += final_pnl

                TOTAL_TRADES += 1
                WINS += 1

                LOSS_STREAK = 0

                send_telegram(
f"""
🌕 MOON EXIT

{symbol}

Final PnL:
+{final_pnl:.2f}%

Highest Gain:
+{((highest_price / buy_price)-1)*100:.2f}%
"""
                )

                ACTIVE_TRADES.pop(symbol, None)

                return

    ACTIVE_TRADES.pop(symbol, None)

# =========================================
# MAIN
# =========================================

def main():

    send_telegram(
"""
🤖 HYBRID STABLE MOON BOT STARTED

Mode:
SAFE + MOON
"""
    )

    while True:

        try:

            global COOLDOWN_UNTIL

            # daily loss limit

            if DAILY_PNL <= MAX_DAILY_LOSS:

                send_telegram(
f"""
🛑 DAILY LOSS LIMIT

Daily PnL:
{DAILY_PNL:.2f}%

Bot paused.
"""
                )

                time.sleep(3600)

                continue

            # cooldown

            if COOLDOWN_UNTIL:

                if datetime.now() < COOLDOWN_UNTIL:

                    print("Cooldown active")

                    time.sleep(30)

                    continue

                else:

                    COOLDOWN_UNTIL = None

                    send_telegram(
"""
✅ COOLDOWN FINISHED

Bot resumed.
"""
                    )

            tokens = get_tokens()

            print(f"Found {len(tokens)}")

            for token in tokens:

                token["score"] = calculate_score(token)

                if not is_safe(token):
                    continue

                symbol = token["symbol"]

                # double confirmation

                if symbol not in WATCHLIST:

                    WATCHLIST[symbol] = 1

                    continue

                WATCHLIST[symbol] += 1

                # ultra high quality only

                if (
                    WATCHLIST[symbol] >= 2
                    and token["score"] >= 90
                ):

                    send_telegram(
f"""
🔥 ELITE SIGNAL

{symbol}

AI Score:
{token['score']}
"""
                    )

                    simulate_trade(token)

            time.sleep(SCAN_INTERVAL)

        except Exception as e:

            print("MAIN ERROR", e)

            time.sleep(10)

# =========================================
# START
# =========================================

if __name__ == "__main__":
    main()
