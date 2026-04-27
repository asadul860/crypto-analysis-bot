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

# ১. টেলিগ্রাম বট টোকেন
API_TOKEN = os.environ.get("BOT_TOKEN", "8537303678:AAFVsbISMZZkfCMlqcJ9EQScz5OjbIwrXvs")
bot = telebot.TeleBot(API_TOKEN)

# ২. ওয়েব সার্ভার
app = Flask('')
@app.route('/')
def home(): return "Multi-Market Trader Bot is Active!"

def run_web():
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)

# ৩. ডাটা ফেচ ফাংশন (ক্রিপ্টো ও ফরেক্স আলাদা করা হয়েছে)
def fetch_market_data(symbol):
    symbol = symbol.upper()
    
    # ফরেক্স এবং কমোডিটি লিস্ট
    forex_map = {'GOLD': 'GC=F', 'SILVER': 'SI=F', 'EURUSD': 'EURUSD=X', 'GBPUSD': 'GBPUSD=X', 'USDJPY': 'JPY=X'}
    
    # যদি ফরেক্স হয়
    if symbol in forex_map or (len(symbol) == 6 and symbol.isalpha()):
        search_symbol = forex_map.get(symbol, f"{symbol}=X")
        try:
            data = yf.download(search_symbol, period="5d", interval="1h", progress=False)
            if not data.empty:
                # কলামের নাম ক্লিন করা (Multi-index সমস্যা সমাধানের জন্য)
                df = data.copy()
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df.columns = [col.lower() for col in df.columns]
                return df, symbol
        except: pass

    # যদি ক্রিপ্টো হয়
    crypto_symbol = f"{symbol}/USDT" if "/" not in symbol else symbol
    exchange = ccxt.binance({'options': {'defaultType': 'spot'}})
    try:
        bars = exchange.fetch_ohlcv(crypto_symbol, timeframe='1h', limit=100)
        if bars:
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            # নিশ্চিত করা যে সব ডাটা ফ্লোট হিসেবে আছে
            for col in ['open', 'high', 'low', 'close']:
                df[col] = df[col].astype(float)
            return df, crypto_symbol
    except Exception as e:
        print(f"Crypto Error: {e}")
        raise Exception("Data not found")

# ৪. অ্যানালাইসিস লজিক
def analyze_market(df):
    close_prices = df['close']
    high_prices = df['high']
    low_prices = df['low']

    # ইন্ডিকেটর
    bb = ta.volatility.BollingerBands(close=close_prices, window=20, window_dev=2)
    df['bb_high'], df['bb_low'] = bb.bollinger_hband(), bb.bollinger_lband()
    df['rsi'] = ta.momentum.rsi(close=close_prices, window=14)
    df['ema_50'] = ta.trend.ema_indicator(close=close_prices, window=50)
    adx_ind = ta.trend.ADXIndicator(high=high_prices, low=low_prices, close=close_prices, window=14)
    df['adx'] = adx_ind.adx()

    last = df.iloc[-1]
    close, rsi, adx = float(last['close']), float(last['rsi']), float(last['adx'])
    bb_low, bb_high, ema_50 = float(last['bb_low']), float(last['bb_high']), float(last['ema_50'])

    action, target, sl, advice = "⏳ WAIT (NO ENTRY)", "N/A", "N/A", "মার্কেট এখন নিউট্রাল।"

    if close <= (bb_low * 1.001) and rsi < 35:
        action = "🟢 BUY / LONG"
        target = round(close * 1.012, 4) if close > 1 else round(close * 1.012, 6)
        sl = round(close * 0.994, 4) if close > 1 else round(close * 0.994, 6)
        advice = "প্রাইস সাপোর্ট জোনে এবং ওভারসোল্ড। বাউন্স হওয়ার সম্ভাবনা বেশি।"
    elif close >= (bb_high * 0.999) and rsi > 65:
        action = "🔴 SELL / SHORT"
        target = round(close * 0.988, 4) if close > 1 else round(close * 0.988, 6)
        sl = round(close * 1.006, 4) if close > 1 else round(close * 1.006, 6)
        advice = "প্রাইস রেজিস্ট্যান্স জোনে এবং ওভারবট। কারেকশন হতে পারে।"
    elif adx > 25 and close > ema_50:
        action = "📈 TREND BUY"
        target = round(close * 1.008, 4) if close > 1 else round(close * 1.008, 6)
        sl = round(ema_50 * 0.996, 4) if close > 1 else round(ema_50 * 0.996, 6)
        advice = "মার্কেট শক্তিশালী আপট্রেন্ডে আছে। ট্রেন্ডের সাথে ট্রেড করা নিরাপদ।"

    return {
        "price": close, "action": action, "target": target, 
        "sl": sl, "advice": advice, "rsi": round(rsi, 1), "adx": round(adx, 1)
    }

# ৫. কমান্ড হ্যান্ডলার
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "📊 **Trader Bot Pro**\n\nলিখুন:\n`/analyze btc` (ক্রিপ্টো)\n`/analyze gold` (ফরেক্স)", parse_mode="Markdown")

@bot.message_handler(commands=['analyze'])
def get_analysis(message):
    try:
        args = message.text.split()
        target_coin = args[1] if len(args) > 1 else "BTC"
        
        # ডাটা ফেচিং
        df, final_symbol = fetch_market_data(target_coin)
        data = analyze_market(df)
        
        bd_time = datetime.now(pytz.timezone('Asia/Dhaka')).strftime('%I:%M %p, %d %b %Y')
        
        response = (
            f"📊 **{final_symbol} Market Signal**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⏰ **Time:** {bd_time} (BD)\n"
            f"💰 **Price:** {data['price']}\n\n"
            f"🎯 **Action:** {data['action']}\n"
            f"📈 **Target:** {data['target']}\n"
            f"🛑 **Stop Loss:** {data['sl']}\n\n"
            f"⚡ **RSI:** {data['rsi']} | **ADX:** {data['adx']}\n"
            f"💡 **Advice:** {data['advice']}\n"
            f"━━━━━━━━━━━━━━━"
        )
        bot.send_message(message.chat.id, response, parse_mode="Markdown")
    except Exception as e:
        print(f"Error: {e}")
        bot.send_message(message.chat.id, "❌ ডাটা পাওয়া যায়নি।\nসঠিক নাম দিন (যেমন: btc, sol, gold, eurusd)")

if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)
