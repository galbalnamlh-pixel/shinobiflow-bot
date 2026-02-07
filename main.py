import time
import requests
from datetime import datetime

# =========================
# CONFIG
# =========================
TELEGRAM_TOKEN = "8420448991:AAG2lkBDA9gUZzHblSbQ48kAbQpYqX7BwJo"
CHAT_ID = "5837332461"

BINANCE_API = "https://api.binance.com/api/v3"
INTERVAL_MAIN = "5m"
INTERVAL_CONFIRM = "15m"

EXCLUDED_COINS = ["BTC", "ETH", "BNB", "SOL"]
MIN_VOLUME_USDT = 5_000_000  # فلترة العملات الميتة
CHECK_DELAY = 60  # ثانية

sent_alerts = set()

# =========================
# HELPERS
# =========================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    requests.post(url, json=payload, timeout=10)


def get_symbols():
    data = requests.get(f"{BINANCE_API}/exchangeInfo").json()
    symbols = []
    for s in data["symbols"]:
        if s["status"] != "TRADING":
            continue
        if not s["symbol"].endswith("USDT"):
            continue
        base = s["baseAsset"]
        if base in EXCLUDED_COINS:
            continue
        symbols.append(s["symbol"])
    return symbols


def get_klines(symbol, interval, limit=50):
    url = f"{BINANCE_API}/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    return requests.get(url, params=params, timeout=10).json()


def get_ticker(symbol):
    url = f"{BINANCE_API}/ticker/24hr"
    params = {"symbol": symbol}
    return requests.get(url, params=params, timeout=10).json()


# =========================
# STRATEGY (بسيطة + حقيقية)
# =========================
def analyze(symbol):
    klines_5m = get_klines(symbol, INTERVAL_MAIN)
    klines_15m = get_klines(symbol, INTERVAL_CONFIRM)

    if len(klines_5m) < 20 or len(klines_15m) < 20:
        return None

    closes_5m = [float(k[4]) for k in klines_5m]
    volumes_5m = [float(k[5]) for k in klines_5m]

    closes_15m = [float(k[4]) for k in klines_15m]

    # اتجاه بسيط
    trend_5m = closes_5m[-1] > closes_5m[-5]
    trend_15m = closes_15m[-1] > closes_15m[-5]

    # فوليوم
    avg_vol = sum(volumes_5m[-10:]) / 10
    last_vol = volumes_5m[-1]

    if trend_5m and trend_15m and last_vol > avg_vol * 1.5:
        entry = closes_5m[-1]
        tp1 = round(entry * 1.02, 6)
        tp2 = round(entry * 1.04, 6)
        tp3 = round(entry * 1.06, 6)
        sl = round(entry * 0.97, 6)

        return {
            "entry": entry,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "sl": sl
        }

    return None


# =========================
# MAIN LOOP
# =========================
def run():
    send_telegram("🥷 <b>ShinobiFlow</b>\nتم تشغيل البوت بنجاح\nBinance Spot | فريم 5m / 15m")

    symbols = get_symbols()

    while True:
        try:
            for symbol in symbols:
                ticker = get_ticker(symbol)
                volume_usdt = float(ticker["quoteVolume"])

                if volume_usdt < MIN_VOLUME_USDT:
                    continue

                signal = analyze(symbol)
                if not signal:
                    continue

                key = f"{symbol}_{int(signal['entry'])}"
                if key in sent_alerts:
                    continue

                sent_alerts.add(key)

                message = f"""
🚨 <b>فرصة فورية (Spot)</b>

🪙 الزوج: <b>{symbol}</b>
⏱️ الفريم: 5 دقائق (تأكيد 15)
💰 دخول: <b>{signal['entry']}</b>

🎯 الأهداف:
1️⃣ {signal['tp1']}
2️⃣ {signal['tp2']}
3️⃣ {signal['tp3']}

🛑 وقف الخسارة:
{signal['sl']}

📊 حجم التداول 24h:
{int(volume_usdt):,} USDT

🕒 التوقيت:
{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC

⚔️ ShinobiFlow – تحرّك بهدوء
"""
                send_telegram(message)

            time.sleep(CHECK_DELAY)

        except Exception as e:
            send_telegram(f"⚠️ خطأ مؤقت:\n{e}")
            time.sleep(30)


if __name__ == "__main__":
    run()
