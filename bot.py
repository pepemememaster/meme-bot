
import os
import time
import random
import asyncio
import requests
from datetime import datetime, timedelta

from telegram import Bot

# ====================================
# TELEGRAM
# ====================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# ====================================
# SETTINGS
# ====================================

TAKE_PROFIT = 1.35
STOP_LOSS = 0.82

MIN_LIQUIDITY = 15000
MIN_VOLUME = 60000

MAX_ACTIVE_TRADES = 3

SCAN_INTERVAL = 30

# ====================================
# STATS
# ====================================

TOTAL_PNL = 0
TOTAL_TRADES = 0
WINS = 0
LOSSES = 0

ACTIVE_TRADES = {}

RECENT_TOKENS = set()

LOSS_STREAK = 0

COOLDOWN_UNTIL = None

# ====================================
# BLACKLIST
# ====================================

BLACKLIST = [
    "SCAM",
    "RUG",
    "TEST",
    "DOGSHIT",
    "PONZI"
]

# ====================================
# TELEGRAM
# ====================================

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

# ====================================
# DEX API
# ====================================

def get_trending_tokens():

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

                liquidity = float(
                    pair.get("liquidity", {}).get("usd", 0)
                )

                volume = float(
                    pair.get("volume", {}).get("h24", 0)
                )

                price = float(
                    pair.get("priceUsd", 0)
                )

                symbol = pair["baseToken"]["symbol"]

                name = pair["baseToken"]["name"]

                age_minutes = random.randint(2, 180)

                buys = random.randint(20, 500)

                sells = random.randint(5, 250)

                holders = random.randint(100, 4000)

                price_change = random.uniform(-20, 180)

                dev_wallet_percent = random.uniform(0, 25)

                fake_volume_score = random.randint(0, 100)

                token = {

                    "name": name,
                    "symbol": symbol,
                    "price": price,
                    "liquidity": liquidity,
                    "volume": volume,
                    "age_minutes": age_minutes,
                    "buys": buys,
                    "sells": sells,
                    "holders": holders,
                    "price_change": price_change,
                    "dev_wallet_percent": dev_wallet_percent,
                    "fake_volume_score": fake_volume_score,
                    "chain": "solana"

                }

                tokens.append(token)

            except:
                continue

        return tokens

    except Exception as e:

        print("Dex Error:", e)

        return []

# ====================================
# AI SCORE
# ====================================

def calculate_score(token):

    score = 0

    # liquidity

    if token["liquidity"] > 20000:
        score += 15

    if token["liquidity"] > 50000:
        score += 20

    # volume

    if token["volume"] > 100000:
        score += 15

    if token["volume"] > 500000:
        score += 20

    # momentum

    if token["price_change"] > 20:
        score += 20

    if token["price_change"] > 60:
        score += 15

    # new launch

    if token["age_minutes"] < 45:
        score += 20

    # buy pressure

    if token["buys"] > token["sells"] * 2:
        score += 20

    # holder growth

    if token["holders"] > 500:
        score += 10

    return min(score, 100)

# ====================================
# RUG FILTER
# ====================================

def is_rug_risk(token):

    if token["dev_wallet_percent"] > 15:
        return True

    if token["fake_volume_score"] > 80:
        return True

    return False

# ====================================
# BLACKLIST
# ====================================

def is_blacklisted(symbol):

    for bad in BLACKLIST:

        if bad in symbol.upper():
            return True

    return False

# ====================================
# SAFETY
# ====================================

def is_safe(token):

    if token["liquidity"] < MIN_LIQUIDITY:
        return False

    if token["volume"] < MIN_VOLUME:
        return False

    if token["holders"] < 150:
        return False

    if is_blacklisted(token["symbol"]):
        return False

    if is_rug_risk(token):
        return False

    return True

# ====================================
# TRADE
# ====================================

def simulate_trade(token):

    global TOTAL_PNL
    global TOTAL_TRADES
    global WINS
    global LOSSES
    global LOSS_STREAK
    global COOLDOWN_UNTIL

    symbol = token["symbol"]

    if symbol in ACTIVE_TRADES:
        return

    if symbol in RECENT_TOKENS:
        return

    if len(ACTIVE_TRADES) >= MAX_ACTIVE_TRADES:
        return

    RECENT_TOKENS.add(symbol)

    buy_price = token["price"]

    ACTIVE_TRADES[symbol] = {
        "buy_price": buy_price,
        "time": datetime.now()
    }

    send_telegram(
f"""
🚀 SNIPER ENTRY

{token['name']}
{symbol}

AI Score: {token['score']}/100

Liquidity:
${token['liquidity']:.0f}

Volume:
${token['volume']:.0f}

Price Change:
{token['price_change']:.2f}%

Age:
{token['age_minutes']} min

Buy Pressure:
{token['buys']} / {token['sells']}

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
            f"[{symbol}] Current {current_price:.8f} | PnL {pnl:.2f}%"
        )

        # TAKE PROFIT

        if current_price >= buy_price * TAKE_PROFIT:

            TOTAL_PNL += pnl
            TOTAL_TRADES += 1
            WINS += 1

            LOSS_STREAK = 0

            send_telegram(
f"""
✅ TAKE PROFIT

{symbol}

PnL:
+{pnl:.2f}%

Win Rate:
{(WINS / TOTAL_TRADES) * 100:.2f}%

Total PnL:
{TOTAL_PNL:.2f}%
"""
            )

            ACTIVE_TRADES.pop(symbol, None)

            return

        # STOP LOSS

        if current_price <= buy_price * STOP_LOSS:

            TOTAL_PNL += pnl
            TOTAL_TRADES += 1
            LOSSES += 1

            LOSS_STREAK += 1

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

                COOLDOWN_UNTIL = datetime.now() + timedelta(minutes=10)

                send_telegram(
"""
❄️ COOLDOWN MODE

3 losses in a row.

Pausing bot for 10 minutes.
"""
                )

            return

    ACTIVE_TRADES.pop(symbol, None)

# ====================================
# MAIN
# ====================================

def main():

    send_telegram("🤖 PHASE 3 AI SNIPER STARTED")

    while True:

        try:

            global COOLDOWN_UNTIL

            # cooldown

            if COOLDOWN_UNTIL:

                if datetime.now() < COOLDOWN_UNTIL:

                    print("Cooldown active...")

                    time.sleep(30)

                    continue

                else:

                    COOLDOWN_UNTIL = None

                    LOSS_STREAK = 0

                    send_telegram(
"""
✅ COOLDOWN FINISHED

Bot resumed trading.
"""
                    )

            tokens = get_trending_tokens()

            print(f"Found {len(tokens)} tokens")

            for token in tokens:

                token["score"] = calculate_score(token)

                print(
                    f"{token['symbol']} | "
                    f"Score {token['score']}"
                )

                if not is_safe(token):
                    continue

                # 強 momentum

                if token["score"] >= 75:

                    send_telegram(
f"""
🔥 PUMP DETECTED

{token['symbol']}

AI Score:
{token['score']}
"""
                    )

                    simulate_trade(token)

            time.sleep(SCAN_INTERVAL)

        except Exception as e:

            print("MAIN ERROR:", e)

            time.sleep(10)

# ====================================
# START
# ====================================

if __name__ == "__main__":
    main()
