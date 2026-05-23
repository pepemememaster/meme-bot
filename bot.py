import asyncio
import random
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# =========================================
# CONFIG
# =========================================

BOT_TOKEN = "8831478002:AAFSDWIKXlySdPWwSdBtKufJasVq9--RON8"
CHAT_ID = "5034825126"

TAKE_PROFIT = 60
STOP_LOSS = -20

MIN_LIQUIDITY = 500
MAX_LIQUIDITY = 15000

MIN_VOLUME_24H = 1000
MIN_BUYS = 2
MAX_SELL_RATIO = 1.5

CHECK_INTERVAL = 60

MAX_CONSECUTIVE_LOSSES = 5

# =========================================
# GLOBALS
# =========================================

paper_trades = 0
wins = 0
losses = 0
consecutive_losses = 0
pnl_total = 0

paused = False

active_positions = {}
recent_tokens = set()

# =========================================
# TELEGRAM COMMANDS
# =========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Meme Bot Running")

async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global paused
    paused = True
    await update.message.reply_text("⏸ Bot paused")

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global paused
    paused = False
    await update.message.reply_text("▶️ Bot resumed")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = f"""
📊 BOT STATS

Trades: {paper_trades}
Wins: {wins}
Losses: {losses}
PnL: {pnl_total:.2f}%
Consecutive Losses: {consecutive_losses}

Active Positions: {len(active_positions)}
"""

    await update.message.reply_text(text)

async def positions(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not active_positions:
        await update.message.reply_text("No active positions")
        return

    text = "📈 ACTIVE POSITIONS\n\n"

    for token, data in active_positions.items():

        pnl = (
            (data["current_price"] - data["entry_price"])
            / data["entry_price"]
        ) * 100

        text += f"""
Token: {token}

Entry: {data['entry_price']}
Current: {data['current_price']}

PnL: {pnl:.2f}%

Liquidity: ${data.get('liquidity', 0)}

"""

    await update.message.reply_text(text)

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = f"""
📜 HISTORY

Trades: {paper_trades}
Wins: {wins}
Losses: {losses}

Total PnL: {pnl_total:.2f}%
"""

    await update.message.reply_text(text)

# =========================================
# FETCH TOKENS
# =========================================

def fetch_tokens():

    try:

        url = "https://api.dexscreener.com/token-profiles/latest/v1"

        response = requests.get(url, timeout=10)

        data = response.json()

        pairs = data if isinstance(data, list) else []

        valid_tokens = []

        for pair in pairs:

            try:

                token_address = pair.get("tokenAddress")
                if pair.get("chainId") != "solana":
                    continue
                if not token_address:
                    continue

                pair_url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"

                pair_response = requests.get(pair_url, timeout=10)

                pair_data = pair_response.json()

                dex_pairs = pair_data.get("pairs", [])

                if not dex_pairs:
                    continue

                best_pair = dex_pairs[0]

                price = float(best_pair.get("priceUsd", 0))

                liquidity = float(
                    best_pair.get("liquidity", {}).get("usd", 0)
                )

                volume = float(
                    best_pair.get("volume", {}).get("h24", 0)
                )

                buys = int(
                    best_pair.get("txns", {}).get("h24", {}).get("buys", 0)
                )

                sells = int(
                    best_pair.get("txns", {}).get("h24", {}).get("sells", 0)
                )

                if liquidity < MIN_LIQUIDITY:
                    continue

                if liquidity > MAX_LIQUIDITY:
                    continue

                if volume < MIN_VOLUME_24H:
                    continue

                if buys < MIN_BUYS:
                    continue

                sell_ratio = sells / buys if buys > 0 else 999

                if sell_ratio > MAX_SELL_RATIO:
                    continue

                valid_tokens.append({
                    "token": token_address,
                    "price": price,
                    "liquidity": liquidity,
                    "volume": volume,
                    "buys": buys,
                    "sells": sells,
                })

            except Exception as e:

                print(f"PAIR ERROR: {e}")

                continue

        print(f"FOUND {len(valid_tokens)} TOKENS FROM API")

        return valid_tokens[:30]

    except Exception as e:

        print(f"FETCH ERROR: {e}")

        return []

# =========================================
# PRICE UPDATE
# =========================================

def get_current_price(token_address):

    try:

        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"

        response = requests.get(url, timeout=10)

        data = response.json()

        pairs = data.get("pairs", [])

        if not pairs:
            return None

        best_pair = pairs[0]

        return float(best_pair.get("priceUsd", 0))

    except Exception as e:

        print(f"PRICE ERROR: {e}")

        return None

# =========================================
# MAIN LOOP
# =========================================

async def trading_loop(app):

    global paper_trades
    global wins
    global losses
    global pnl_total
    global consecutive_losses

    while True:

        try:

            if paused:

                await asyncio.sleep(10)

                continue

            if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:

                print("MAX CONSECUTIVE LOSSES REACHED")

                await asyncio.sleep(60)

                continue

            tokens = fetch_tokens()

            if not tokens:

                print("NO TOKENS FOUND")

                await asyncio.sleep(20)

                continue

            # =================================
            # OPEN POSITIONS
            # =================================

            for token_data in tokens[:5]:

                token_name = token_data["token"]

                if token_name in active_positions:
                    continue

                if token_name in recent_tokens:
                    continue

                entry_price = token_data["price"]

                if entry_price <= 0:
                    continue

                # 模擬滑點
                simulated_entry = entry_price * random.uniform(1.01, 1.03)

                active_positions[token_name] = {
                    "entry_price": simulated_entry,
                    "current_price": simulated_entry,
                    "liquidity": token_data["liquidity"],
                }

                recent_tokens.add(token_name)

                paper_trades += 1

                message = f"""
🚀 PAPER BUY

Token:
{token_name}

Entry:
{simulated_entry:.10f}

Liquidity:
${token_data['liquidity']:.0f}

Volume:
${token_data['volume']:.0f}

Buys:
{token_data['buys']}

Sells:
{token_data['sells']}
"""

                try:
                    await app.bot.send_message(chat_id=CHAT_ID, text=message)
                except:
                    pass

            # =================================
            # CHECK POSITIONS
            # =================================

            remove_list = []

            for token_name, data in active_positions.items():

                current_price = get_current_price(token_name)

                if not current_price:
                    continue

                data["current_price"] = current_price

                pnl = (
                    (current_price - data["entry_price"])
                    / data["entry_price"]
                ) * 100

                # 模擬 rug fail sell
                rug_chance = random.randint(1, 100)

                if rug_chance <= 5:
                    pnl = -99

                # TAKE PROFIT
                if pnl >= TAKE_PROFIT:

                    wins += 1
                    consecutive_losses = 0
                    pnl_total += pnl

                    remove_list.append(token_name)

                    try:
                        await app.bot.send_message(
                            chat_id=CHAT_ID,
                            text=f"""
✅ TAKE PROFIT

Token:
{token_name}

PnL:
{pnl:.2f}%
"""
                        )
                    except:
                        pass

                # STOP LOSS
                elif pnl <= STOP_LOSS:

                    losses += 1
                    consecutive_losses += 1
                    pnl_total += pnl

                    remove_list.append(token_name)

                    try:
                        await app.bot.send_message(
                            chat_id=CHAT_ID,
                            text=f"""
❌ STOP LOSS

Token:
{token_name}

PnL:
{pnl:.2f}%
"""
                        )
                    except:
                        pass

            for token in remove_list:

                if token in active_positions:
                    del active_positions[token]

            if len(recent_tokens) > 200:
                recent_tokens.clear()

            await asyncio.sleep(CHECK_INTERVAL)

        except Exception as e:

            print(f"LOOP ERROR: {e}")

            await asyncio.sleep(10)

# =========================================
# MAIN
# =========================================
async def post_init(application):
    asyncio.create_task(trading_loop(application))

def main():

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pause", pause))
    app.add_handler(CommandHandler("resume", resume))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("positions", positions))
    app.add_handler(CommandHandler("history", history))

    print("BOT STARTED")

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
