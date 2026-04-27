import os
import time
import pytz
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
def home(): return "Bot is Online!"

def run_web():
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)

# ৩. ডাটা ফেচ ফাংশন (উন্নত ও সহজতর)
def fetch_market_data(symbol):
    symbol = symbol.upper()
    
    # সিম্বল ম্যাপিং
    forex_map = {'GOLD': 'GC=F', 'SILVER': 'SI=F', 'EURUSD': 'EURUSD=X', 'GBPUSD': 'GBPUSD=X'}
    
    if symbol in forex_map:
        search_symbol = forex_map[symbol]
    elif len(symbol) == 6 and symbol.isalpha(): # ফরেক্স পেয়ার
        search_symbol = f"{symbol}=X"
    else: # ক্রিপ্টো পেয়ার (BTC, ETH, ইত্যাদি)
        search_symbol = f"{symbol}-USD"

    try:
        # Yahoo Finance থেকে ডাটা সংগ্রহ (এটি ক্রিপ্টো ও ফরেক্স দুইটাই দেয়)
        data = yf.download(search_symbol, period="5d", interval="1h", progress=False)
        
        if not data.empty:
            df = data.copy()
            # মাল্টি-ইনডেক্স কলাম ফিক্স
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = [col.lower() for col in df.columns]
            return df, symbol
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
    
    raise Exception("Data not found")

# ৪. অ্যানালাইসিস লজিক
def analyze_market(df):
    # ডাটা নিশ্চিত করা
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)

    # ইন্ডিকেটর
    bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['bb_high'], df['bb_low'] = bb.bollinger_hband(), bb.bollinger_lband()
    df['rsi'] = ta.momentum.rsi(close=df['close'], window=14)
    df['ema_50'] = ta.trend.ema_indicator(close=df['close'], window=50)
    adx_obj = ta.trend.ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=14)
    df['adx'] = adx_obj.adx()

    last = df.iloc[-1]
    close, rsi, adx = last['close'], last['rsi'], last['adx']
    bb_low, bb_high, ema_50 = last['bb_low'], last['bb_high'], last['ema_50']

    action, target, sl, advice = "⏳ WAIT (NO ENTRY)", "N/A", "N/A", "মার্কেট এখন নিউট্রাল।"

    if close <= (bb_low * 1.001) and rsi < 35:
        action, target, sl = "🟢 BUY / LONG", round(close * 1.015, 4), round(close * 0.992, 4)
        advice = "প্রাইস সাপোর্ট জোনে। বাউন্স হওয়ার সম্ভাবনা বেশি।"
    elif close >= (bb_high * 0.999) and rsi > 65:
        action, target, sl = "🔴 SELL / SHORT", round(close * 0.985, 4), round(close * 1.008, 4)
        advice = "প্রাইস রেজিস্ট্যান্স জোনে। কারেকশন হতে পারে।"
    elif adx > 25 and close > ema_50:
        action, target, sl = "📈 TREND BUY", round(close * 1.01, 4), round(ema_50 * 0.995, 4)
        advice = "মার্কেট শক্তিশালী আপট্রেন্ডে আছে।"

    return {
        "price": round(close, 4), "action": action, "target": target, 
        "sl": sl, "advice": advice, "rsi": round(rsi, 1), "adx": round(adx, 1)
    }

# ৫. কমান্ড হ্যান্ডলার
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "📊 **Trader Bot Pro**\nসিগন্যাল পেতে লিখুন:\n`/analyze btc` (ক্রিপ্টো)\n`/analyze gold` (ফরেক্স)", parse_mode="Markdown")

@bot.message_handler(commands=['analyze'])
def get_analysis(message):
    try:
        args = message.text.split()
        target = args[1] if len(args) > 1 else "BTC"
        
        df, final_symbol = fetch_market_data(target)
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
    except:
        bot.send_message(message.chat.id, "❌ ডাটা পাওয়া যায়নি।\nbtc, eth, gold, eurusd লিখে ট্রাই করুন।")

if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)
