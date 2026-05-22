
import os
import time
import random
import requests
from telegram import Bot

# ===== 基本設定 =====

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=TELEGRAM_BOT_TOKEN)

TAKE_PROFIT = 1.25
STOP_LOSS = 0.90

MIN_LIQUIDITY = 20000
MIN_VOLUME = 50000

SCAN_INTERVAL = 30

# ===== 統計 =====

TOTAL_PNL = 0
TOTAL_TRADES = 0
WINS = 0
LOSSES = 0

ACTIVE_TRADES = {}

BLACKLIST = [
    "SCAM",
    "RUG",
    "TEST"
]

# ===== Telegram =====

def send_telegram(msg):
    print(msg)

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=msg
            )
        except Exception as e:
            print(e)

# ===== Rug Filter =====

def is_blacklisted(symbol):
    for bad in BLACKLIST:
        if bad in symbol.upper():
            return True
    return False

# ===== 熱門幣 =====

def get_trending_tokens():

    url = "https://api.dexscreener.com/latest/dex/search?q=solana"

    try:
        response = requests.get(url)

        if response.status_code != 200:
            return []

        data = response.json()

    except:
        return []

    pairs = data.get("pairs", [])

    tokens = []

    for pair in pairs[:20]:

        try:

            liquidity = float(
                pair.get("liquidity", {}).get("usd", 0)
            )

            volume = float(
                pair.get("volume", {}).get("h24", 0)
            )

            price = float(pair.get("priceUsd", 0))

            symbol = pair["baseToken"]["symbol"]

            name = pair["baseToken"]["name"]

            chain = pair.get("chainId", "unknown")

            if liquidity < MIN_LIQUIDITY:
                continue

            if volume < MIN_VOLUME:
                continue

            if is_blacklisted(symbol):
                continue

            token = {
                "name": name,
                "symbol": symbol,
                "price": price,
                "liquidity": liquidity,
                "volume": volume,
                "chain": chain
            }

            tokens.append(token)

        except:
            continue

    return tokens

# ===== 安全檢查 =====

def is_safe(token):

    if token["liquidity"] < MIN_LIQUIDITY:
        return False

    return True

# ===== 模擬交易 =====

def simulate_trade(token):

    global TOTAL_PNL
    global TOTAL_TRADES
    global WINS
    global LOSSES

    symbol = token["symbol"]

    if symbol in ACTIVE_TRADES:
        return

    buy_price = token["price"]

    ACTIVE_TRADES[symbol] = True

    send_telegram(
        f"""
🚀 AUTO BUY

Name: {token['name']}
Symbol: {symbol}
Chain: {token['chain']}

Liquidity: ${token['liquidity']:.0f}
24h Volume: ${token['volume']:.0f}

Buy Price: ${buy_price:.8f}
"""
    )

    current_price = buy_price

    for i in range(20):

        time.sleep(2)

        move = random.uniform(0.96, 1.08)

        current_price *= move

        pnl = ((current_price / buy_price) - 1) * 100

        print(
            f"[{symbol}] Current: {current_price:.8f} | PnL: {pnl:.2f}%"
        )

        if current_price >= buy_price * TAKE_PROFIT:

            TOTAL_PNL += pnl
            TOTAL_TRADES += 1
            WINS += 1

            send_telegram(
                f"""
✅ TAKE PROFIT

{symbol}

PnL: +{pnl:.2f}%
"""
            )

            break

        if current_price <= buy_price * STOP_LOSS:

            TOTAL_PNL += pnl
            TOTAL_TRADES += 1
            LOSSES += 1

            send_telegram(
                f"""
🛑 STOP LOSS

{symbol}

PnL: {pnl:.2f}%
"""
            )

            break

    ACTIVE_TRADES.pop(symbol, None)

    if TOTAL_TRADES > 0:

        win_rate = (WINS / TOTAL_TRADES) * 100

        send_telegram(
            f"""
📊 STATS

Total Trades: {TOTAL_TRADES}

Wins: {WINS}
Losses: {LOSSES}

Win Rate: {win_rate:.2f}%

Total PnL: {TOTAL_PNL:.2f}%
"""
        )

# ===== 主循環 =====

def main():

    send_telegram("🤖 Meme Sniper Started")

    while True:

        try:

            tokens = get_trending_tokens()

            print(f"Found {len(tokens)} tokens")

            for token in tokens:

                print(
                    f"SAFE => {token['symbol']} | "
                    f"Liq ${token['liquidity']:.0f}"
                )

                if is_safe(token):

                    simulate_trade(token)

            time.sleep(SCAN_INTERVAL)

        except Exception as e:

            print(e)

            time.sleep(10)

# ===== 啟動 =====

if __name__ == "__main__":
    main()
