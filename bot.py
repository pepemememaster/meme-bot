
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

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# ===== 模擬 Token 資料 =====
WATCHLIST = [
    {
        "name": "ExampleToken",
        "symbol": "EXM",
        "price": 0.01,
        "liquidity": 20000,
        "holders": 500,
        "mint_enabled": False
    }
]

def send_telegram(msg):
    try:
        def send_telegram(msg):
    import asyncio

    try:
        asyncio.run(
            bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=msg
            )
        )
    except Exception as e:
        print(e)
    except Exception as e:
        print("Telegram error:", e)

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
            send_telegram(
                f"✅ Take Profit Hit\n"
                f"{token['symbol']}\n"
                f"PnL: +{pnl:.2f}%"
            )
            return

        if current_price <= buy_price * STOP_LOSS:
            send_telegram(
                f"🛑 Stop Loss Hit\n"
                f"{token['symbol']}\n"
                f"PnL: {pnl:.2f}%"
            )
            return

def main():
    send_telegram("🤖 Meme Bot Started")

    while True:
        for token in WATCHLIST:
            if is_safe(token):
                simulate_trade(token)

        time.sleep(30)

if __name__ == "__main__":
    main()
