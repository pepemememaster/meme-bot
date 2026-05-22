
# Telegram Meme Coin Bot 教學（手機版）

## 功能
- Telegram 通知
- 自動檢查條件
- 模擬買入
- 自動止盈止損
- Railway 可部署

---

# Step 1：建立 Telegram Bot

1. 打開 Telegram
2. 搜尋 `@BotFather`
3. 輸入：

```
/newbot
```

4. 建立完成後會拿到：

```
TELEGRAM_BOT_TOKEN
```

請保存。

---

# Step 2：取得 Chat ID

搜尋：

```
@userinfobot
```

它會給你：

```
CHAT ID
```

保存。

---

# Step 3：安裝 Railway

官方網站：

https://railway.com/

登入後：

1. New Project
2. Deploy from GitHub 或 Upload
3. 上傳這份 bot.py

---

# Step 4：設定環境變數

Railway Variables：

新增：

## TELEGRAM_BOT_TOKEN

填入你的 token

---

## TELEGRAM_CHAT_ID

填入你的 chat id

---

# Step 5：啟動

按：

```
Deploy
```

成功後 Telegram 會收到：

```
🤖 Meme Bot Started
```

---

# Step 6：修改參數

在 bot.py：

## 止盈

```python
TAKE_PROFIT = 1.20
```

代表：

+20%

---

## 止損

```python
STOP_LOSS = 0.88
```

代表：

-12%

---

# 安全建議

建議：
- 小額開始
- 不要 all in
- 不要追已暴漲 meme
- 每日限制交易次數

---

# 建議初始資金

你的情況：

```
0.35 SOL
```

建議：

單次：
- 0.02 ~ 0.03 SOL

最穩。

---

# 後續可擴充

之後你可以加入：
- DexScreener API
- 自動掃描 Trending
- 真實 Solana 下單
- 自動賣出
- AI 熱度分析

