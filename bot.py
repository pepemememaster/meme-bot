import asyncio
import random
import time
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
# Paper Trading Settings
TAKE_PROFIT = 80
STOP_LOSS = -25
# Market Filters
MIN_LIQUIDITY = 3000
MAX_LIQUIDITY = 30000
MIN_VOLUME_24H =5000
MIN_BUYS = 8
MAX_SELL_RATIO = 1.4
MIN_VOLUME_PER_BUY = 80
MAX_TOKEN_AGE_MINUTES = 180
# Runtime
CHECK_INTERVAL = 60
MAX_CONSECUTIVE_LOSSES = 5
AUTO_PAUSE_MINUTES = 30
MAX_ACTIVE_TRADES = 2
# =========================================
# GLOBALS
# =========================================
paper_trades = 0
wins = 0
losses = 0
consecutive_losses = 0
pnl_total = 0
paused = False
pause_until = 0
active_positions = {}
recent_tokens = {}
# =========================================
# TELEGRAM COMMANDS
# =========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Meme Momentum Bot Running")
async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global paused
    paused = True
    await update.message.reply_text("⏸ Bot paused")
async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global paused
    global consecutive_losses
    paused = False
    consecutive_losses = 0
    await update.message.reply_text("▶️ Bot resumed")
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"""
📊 BOT STATS
Trades: {paper_trades}
Wins: {wins}
Losses: {losses}
Winrate:
{(wins / paper_trades * 100) if paper_trades > 0 else 0:.2f}%
PnL:
{pnl_total:.2f}%
Consecutive Losses:
{consecutive_losses}
Active Positions:
{len(active_positions)}
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
Token:
{token}
Entry:
${data['entry_price']:.10f}
Current:
${data['current_price']:.10f}
PnL:
{pnl:.2f}%
Liquidity:
${data['liquidity']:.0f}
Score:
{data['score']:.2f}
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
                pair_url = (
                    f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
                )
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
                    best_pair.get("txns", {})
                    .get("h24", {})
                    .get("buys", 0)
                )
                sells = int(
                    best_pair.get("txns", {})
                    .get("h24", {})
                    .get("sells", 0)
                )
                pair_created = best_pair.get("pairCreatedAt")
                if not pair_created:
                    continue
                token_age_minutes = (
                    (time.time() * 1000 - pair_created)
                    / 1000
                    / 60
                )
                # =================================
                # FILTERS
                # =================================
                if liquidity < MIN_LIQUIDITY:
                    continue
                if liquidity > MAX_LIQUIDITY:
                    continue
                if volume < MIN_VOLUME_24H:
                    continue
                if buys < MIN_BUYS:
                    continue
                if token_age_minutes > MAX_TOKEN_AGE_MINUTES:
                    continue
                sell_ratio = sells / buys if buys > 0 else 999
                if sell_ratio > MAX_SELL_RATIO:
                    continue
                volume_per_buy = volume / buys if buys > 0 else 0
                if volume_per_buy < MIN_VOLUME_PER_BUY:
                    continue
                # =================================
                # MOMENTUM SCORE
                # =================================
                score = (
                    (buys * 2)
                    + (volume / 1000)
                    + (liquidity / 5000)
                    - sells
                )
                valid_tokens.append({
                    "token": token_address,
                    "name": best_pair.get(
                        "baseToken", {}
                    ).get("name", "Unknown"),
                    "symbol": best_pair.get(
                        "baseToken", {}
                    ).get("symbol", "???"),
                    "price": price,
                    "liquidity": liquidity,
                    "volume": volume,
                    "buys": buys,
                    "sells": sells,
                    "score": score,
                    "age": token_age_minutes,
                })
            except Exception as e:
                print(f"PAIR ERROR: {e}")
                continue
        valid_tokens.sort(
            key=lambda x: x["score"],
            reverse=True
        )
        print(f"FOUND {len(valid_tokens)} TOKENS")
        return valid_tokens[:20]
    except Exception as e:
        print(f"FETCH ERROR: {e}")
        return []
# =========================================
# PRICE UPDATE
# =========================================
def get_current_price(token_address):
    try:
        url = (
            f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
        )
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
    global paused
    global pause_until
    while True:
        try:
            current_time = time.time()
            # =================================
            # AUTO RESUME
            # =================================
            if paused and current_time > pause_until:
                paused = False
                consecutive_losses = 0
                try:
                    await app.bot.send_message(
                        chat_id=CHAT_ID,
                        text="▶️ Auto Resume Activated"
                    )
                except:
                    pass
            if paused:
                await asyncio.sleep(10)
                continue
            # =================================
            # LOSS PROTECTION
            # =================================
            if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
                paused = True
                pause_until = (
                    current_time
                    + (AUTO_PAUSE_MINUTES * 60)
                )
                try:
                    await app.bot.send_message(
                        chat_id=CHAT_ID,
                        text=f"""
🛑 AUTO PAUSE
Too many consecutive losses.
Bot paused for:
{AUTO_PAUSE_MINUTES} minutes
"""
                    )
                except:
                    pass
                await asyncio.sleep(30)
                continue
            tokens = fetch_tokens()
            if not tokens:
                print("NO TOKENS FOUND")
                await asyncio.sleep(20)
                continue
            # =================================
            # OPEN POSITIONS
            # =================================
            if len(active_positions) < MAX_ACTIVE_TRADES:
                for token_data in tokens[:2]:
                    token_name = (
                        f"{token_data['name']} "
                        f"(${token_data['symbol']})"
                    )
                    if token_name in active_positions:
                        continue
                    if token_name in recent_tokens:
                        cooldown = (
                            current_time
                            - recent_tokens[token_name]
                        )
                        if cooldown < 3600:
                            continue
                    entry_price = token_data["price"]
                    if entry_price <= 0:
                        continue
                    simulated_entry = (
                        entry_price
                        * random.uniform(1.005, 1.02)
                    )
                    active_positions[token_name] = {
                        "token_address": token_data["token"],
                        "entry_price": simulated_entry,
                        "current_price": simulated_entry,
                        "liquidity": token_data["liquidity"],
                        "score": token_data["score"],
                    }
                    recent_tokens[token_name] = current_time
                    paper_trades += 1
                    message = f"""
🚀 PAPER BUY
Token:
{token_name}
Entry:
${simulated_entry:.10f}
Liquidity:
${token_data['liquidity']:.0f}
Volume:
${token_data['volume']:.0f}
Buys/Sells:
{token_data['buys']} / {token_data['sells']}
Momentum Score:
{token_data['score']:.2f}
Age:
{token_data['age']:.1f} minutes
"""
                    try:
                        await app.bot.send_message(
                            chat_id=CHAT_ID,
                            text=message
                        )
                    except Exception as e:
                        print(f"TG ERROR: {e}")
            # =================================
            # CHECK POSITIONS
            # =================================
            remove_list = []
            for token_name, data in active_positions.items():
                current_price = get_current_price(
                    data["token_address"]
                )
                if not current_price:
                    continue
                data["current_price"] = current_price
                pnl = (
                    (current_price - data["entry_price"])
                    / data["entry_price"]
                ) * 100
                # Simulated Rug Risk
                rug_chance = random.randint(1, 100)
                if rug_chance <= 3:
                    pnl = -99
                # =================================
                # TAKE PROFIT
                # =================================
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
                # =================================
                # STOP LOSS
                # =================================
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
            # Cleanup old cooldowns
            if len(recent_tokens) > 300:
                now = time.time()
                recent_tokens_copy = dict(recent_tokens)
                for token, timestamp in recent_tokens_copy.items():
                    if now - timestamp > 7200:
                        del recent_tokens[token]
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
    print("BOT STARTED")
    app.run_polling(drop_pending_updates=True)
if __name__ == "__main__":
    main()
