# TrendRadar 第二期：AI Stock Radar

## 功能
- 台股 + 美股
- MA20 / MA60 / MA120
- RSI14
- MACD
- 20 日平均成交量
- 60 日突破
- ROE / EPS 成長 / 營收成長
- 0～100 分排序
- Telegram / Slack 通知
- GitHub Actions 每週一～週五自動執行

## GitHub Secrets
至少建立：
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID

可選：
- SLACK_WEBHOOK_URL

## 手動執行
GitHub → Actions → AI Stock Radar → Run workflow

## 本機執行
```bash
uv sync
uv run stock-radar --config config/stock_radar.yaml
```

## 重要
這是「篩選器」而不是自動下單系統。分數規則需要用歷史資料回測後再決定是否採用。
