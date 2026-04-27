import os
import time
import pytz
import ccxt
import pandas as pd
import ta
import telebot
import yfinance as yf
from threading import Thread
from flask import Flask
from datetime import datetime

# ১. টেলিগ্রাম বট টোকেন (রেলওয়ে ভেরিয়েবল থেকে নিবে, না থাকলে ডিফল্ট)
API_TOKEN = os.environ.get("BOT_TOKEN", "8537303678:AAFVsbISMZZkfCMlqcJ9EQScz5OjbIwrXvs")
bot = telebot.TeleBot(API_TOKEN)

# ২. ওয়েব সার্ভার (রেলওয়ে/রেন্ডারের পোর্ট ম্যানেজমেন্ট)
app = Flask('')

@app.route('/')
def home():
    return "Multi-Market Trader Bot is Active!"

def run_web():
    # রেলওয়ে ডিফল্ট পোর্ট ৮০০০ বা ১০০০০ ব্যবহার করে
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)

# ৩. ডাটা ফেচ ফাংশন (Crypto + Forex)
def fetch_market_data(symbol):
    symbol = symbol.upper()
    
    # ফরেক্স ডাটা চেক
    forex_pairs = {'GOLD': 'GC=F', 'SILVER': 'SI=F', 'EURUSD': 'EURUSD=X', 'GBPUSD': 'GBPUSD=X'}
    search_symbol = forex_pairs.get(symbol, f"{symbol}USD=X") if symbol in forex_pairs or not any(c.isdigit() for c in symbol) else symbol

    try:
        data = yf.download(search_symbol, period="5d", interval="1h", progress=False)
        if not data.empty:
            df = data.copy()
            df.columns = [col[0].lower() if isinstance(col, tuple) else col.lower() for col in df.columns]
            return df, search_symbol
    except:
        pass

    # Crypto (CCXT)
    if "/" not in symbol: symbol = f"{symbol}/USDT"
    exchange = ccxt.binance()
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
        if bars:
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            return df, symbol
    except:
        raise Exception("Data not found")

# ৪. সিগন্যাল অ্যানালাইসিস লজিক
def analyze_market(df):
    close_prices = df['close'].astype(float)
    high_prices = df['high'].astype(float)
    low_prices = df['low'].astype(float)

    bb = ta.volatility.BollingerBands(close=close_prices, window=20, window_dev=2)
    df['bb_high'], df['bb_low'] = bb.bollinger_hband(), bb.bollinger_lband()
    df['rsi'] = ta.momentum.rsi(close=close_prices, window=14)
    df['ema_50'] = ta.trend.ema_indicator(close=close_prices, window=50)
    
    last = df.iloc[-1]
    close, rsi, bb_low, bb_high, ema_50 = float(last['close']), float(last['rsi']), float(last['bb_low']), float(last['bb_high']), float(last['ema_50'])

    action, target, sl, advice = "⏳ WAIT", "N/A", "N/A", "মার্কেট এখন নিউট্রাল।"

    if close <= bb_low and rsi < 35:
        action, target, sl = "🟢 BUY / LONG", round(close * 1.012, 5), round(close * 0.994, 5)
        advice = "প্রাইস সাপোর্ট জোনে। বাউন্স হওয়ার সম্ভাবনা আছে।"
    elif close >= bb_high and rsi > 65:
        action, target, sl = "🔴 SELL / SHORT", round(close * 0.988, 5), round(close * 1.006, 5)
        advice = "প্রাইস রেজিস্ট্যান্স জোনে। কারেকশন হতে পারে।"

    return {"price": round(close, 5), "action": action, "target": target, "sl": sl, "advice": advice, "rsi": round(rsi, 1)}

# ৫. কমান্ড হ্যান্ডলার
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "স্বাগতম! ট্রেডিং সিগন্যাল পেতে লিখুন:\n`/analyze btc` বা `/analyze gold`", parse_mode="Markdown")

@bot.message_handler(commands=['analyze'])
def get_analysis(message):
    try:
        args = message.text.split()
        target_coin = args[1] if len(args) > 1 else "BTC"
        df, final_symbol = fetch_market_data(target_coin)
        data = analyze_market(df)
        
        bd_time = datetime.now(pytz.timezone('Asia/Dhaka')).strftime('%I:%M %p, %d %b %Y')
        response = (
            f"📊 **{final_symbol} Signal**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💰 Price: {data['price']}\n"
            f"🎯 Action: {data['action']}\n"
            f"📈 Target: {data['target']}\n"
            f"🛑 SL: {data['sl']}\n"
            f"⚡ RSI: {data['rsi']}\n"
            f"💡 {data['advice']}\n"
            f"━━━━━━━━━━━━━━━"
        )
        bot.send_message(message.chat.id, response, parse_mode="Markdown")
    except:
        bot.send_message(message.chat.id, "❌ ডাটা পাওয়া যায়নি। সঠিক পেয়ার নাম লিখুন।")

# ৬. রান প্রসেস
if __name__ == "__main__":
    # ওয়েব সার্ভার আলাদা থ্রেডে চালু করা
    server_thread = Thread(target=run_web)
    server_thread.daemon = True
    server_thread.start()
    
    print("Bot is starting...")
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)
