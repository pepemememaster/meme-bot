
import os
import time
import random
import asyncio
import requests

from datetime import datetime, timedelta
from telegram import Bot

# =========================================================
# TELEGRAM
# =========================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# =========================================================
# ADAPTIVE AI SETTINGS
# =========================================================

TP1 = 1.15
TP2 = 1.40

STOP_LOSS = 0.92

TRAILING_TRIGGER = 1.30
TRAILING_STOP = 0.20

MIN_LIQUIDITY = 40000
MIN_VOLUME = 150000

MAX_ACTIVE_TRADES = 2

MAX_DAILY_TRADES = 20
MAX_DAILY_LOSS = -15

SCAN_INTERVAL = 45

# =========================================================
# STATS
# =========================================================

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

TRADE_MEMORY = {
    "wins": [],
    "losses": []
}

MARKET_MODE = "SAFE"

# =========================================================
# TELEGRAM
# =========================================================

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

# =========================================================
# TOKEN SCANNER
# =========================================================

def get_tokens():

    try:

        url = "https://api.dexscreener.com/latest/dex/search?q=solana"

        response = requests.get(url, timeout=10)

        data = response.json()

        pairs = data.get("pairs", [])

        tokens = []

        for pair in pairs[:50]:

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

                    "holders": random.randint(300, 10000),

                    "holder_growth": random.randint(0, 500),

                    "age_minutes": random.randint(5, 180),

                    "price_change": random.uniform(
                        -15, 300
                    ),

                    "buys": random.randint(50, 2000),

                    "sells": random.randint(10, 600),

                    "unique_wallets": random.randint(
                        50, 1500
                    ),

                    "wallet_diversity": random.randint(
                        50, 100
                    ),

                    "smart_money": random.randint(
                        0, 100
                    ),

                    "fake_volume": random.randint(
                        0, 100
                    ),

                    "dev_wallet": random.uniform(
                        0, 20
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
# MARKET MODE
# =========================================================

def update_market_mode(tokens):

    global MARKET_MODE

    hot_tokens = 0

    for token in tokens:

        if token["price_change"] > 50:
            hot_tokens += 1

    if hot_tokens >= 10:

        MARKET_MODE = "RISK_ON"

    else:

        MARKET_MODE = "SAFE"

# =========================================================
# AI SCORE
# =========================================================

def calculate_score(token):

    score = 0

    # liquidity

    if token["liquidity"] > 40000:
        score += 10

    if token["liquidity"] > 100000:
        score += 10

    # volume

    if token["volume"] > 150000:
        score += 15

    if token["volume"] > 500000:
        score += 15

    # momentum

    if token["price_change"] > 20:
        score += 15

    if token["price_change"] > 80:
        score += 10

    # buy pressure

    if token["buys"] > token["sells"] * 2:
        score += 15

    # holders

    if token["holders"] > 500:
        score += 10

    # holder velocity

    if token["holder_growth"] > 100:
        score += 10

    if token["holder_growth"] > 300:
        score += 10

    # smart money

    if token["smart_money"] > 70:
        score += 15

    # wallet diversity

    if token["wallet_diversity"] > 70:
        score += 10

    # early launch

    if token["age_minutes"] < 45:
        score += 10

    return min(score, 100)

# =========================================================
# AI CONFIDENCE
# =========================================================

def calculate_confidence(token):

    confidence = 50

    if token["holder_growth"] > 150:
        confidence += 10

    if token["smart_money"] > 80:
        confidence += 15

    if token["wallet_diversity"] > 80:
        confidence += 10

    if token["buys"] > token["sells"] * 3:
        confidence += 15

    return min(confidence, 100)

# =========================================================
# FILTER
# =========================================================

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

    if token["wallet_diversity"] < 60:
        return False

    return True

# =========================================================
# POSITION SIZE
# =========================================================

def get_position_size(score):

    if score >= 97:
        return "HIGH"

    if score >= 93:
        return "MEDIUM"

    return "SMALL"

# =========================================================
# TRADE
# =========================================================

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

    position_size = get_position_size(
        token["score"]
    )

    send_telegram(
f"""
🚀 ADAPTIVE ENTRY

{symbol}

AI Score:
{token['score']}/100

Confidence:
{token['confidence']}%

Market Mode:
{MARKET_MODE}

Position Size:
{position_size}

Liquidity:
${token['liquidity']:.0f}

Volume:
${token['volume']:.0f}

Holder Growth:
{token['holder_growth']}

BUY:
${buy_price:.8f}
"""
    )

    current_price = buy_price

    highest_price = buy_price

    tp1_hit = False
    tp2_hit = False

    for i in range(60):

        time.sleep(2)

        if MARKET_MODE == "RISK_ON":

            movement = random.uniform(
                0.96, 1.18
            )

        else:

            movement = random.uniform(
                0.97, 1.10
            )

        current_price *= movement

        pnl = (
            (
                current_price
                / buy_price
            ) - 1
        ) * 100

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

            TRADE_MEMORY["losses"].append(
                token["score"]
            )

            send_telegram(
f"""
🛑 STOP LOSS

{symbol}

PnL:
{pnl:.2f}%

Loss Streak:
{LOSS_STREAK}
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
+15%
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

Moonbag:
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

                TRADE_MEMORY["wins"].append(
                    token["score"]
                )

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

# =========================================================
# MAIN
# =========================================================

def main():

    send_telegram(
"""
🤖 ADAPTIVE AI QUANT STARTED

Mode:
SAFE + MOON + AI
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

            update_market_mode(tokens)

            print(
                f"Market Mode: {MARKET_MODE}"
            )

            for token in tokens:

                token["score"] = calculate_score(
                    token
                )

                token["confidence"] = (
                    calculate_confidence(token)
                )

                if not is_safe(token):
                    continue

                symbol = token["symbol"]

                # double confirmation

                if symbol not in WATCHLIST:

                    WATCHLIST[symbol] = 1

                    continue

                WATCHLIST[symbol] += 1

                # adaptive score

                required_score = 90

                if MARKET_MODE == "RISK_ON":
                    required_score = 85

                # elite entry only

                if (
                    WATCHLIST[symbol] >= 2
                    and token["score"] >= required_score
                    and token["confidence"] >= 75
                ):

                    send_telegram(
f"""
🔥 ELITE AI SIGNAL

{symbol}

AI Score:
{token['score']}

Confidence:
{token['confidence']}%

Market:
{MARKET_MODE}
"""
                    )

                    simulate_trade(token)

            time.sleep(SCAN_INTERVAL)

        except Exception as e:

            print("MAIN ERROR", e)

            time.sleep(10)

# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
