import ccxt
import pandas as pd
import ta
import telebot
import os
from threading import Thread
from flask import Flask

# ১. টেলিগ্রাম বট সেটআপ
API_TOKEN = '8537303678:AAFVsbISMZZkfCMlqcJ9EQScz5OjbIwrXvs'
bot = telebot.TeleBot(API_TOKEN)

# ২. ছোট একটি ওয়েবসাইট তৈরি (Render এর পোর্ট এরর বন্ধ করার জন্য)
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

# ৩. মার্কেট এনালাইসিস লজিক
exchange = ccxt.binance()

def fetch_data(symbol='BTC/USDT'):
    bars = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    return df

def analyze_market(df):
    indicator_bb = ta.volatility.BollingerBands(close=df["close"], window=20, window_dev=2)
    df['bb_high'] = indicator_bb.bollinger_hband()
    df['bb_low'] = indicator_bb.bollinger_lband()
    
    last_row = df.iloc[-1]
    close = last_row['close']
    upper = last_row['bb_high']
    lower = last_row['bb_low']

    if close <= lower:
        signal = "🚀 Strong BUY (Lower Band)"
    elif close >= upper:
        signal = "🔻 Strong SELL (Upper Band)"
    else:
        signal = "⚖️ Neutral"

    return f"Price: {close}\nUpper: {upper:.2f}\nLower: {lower:.2f}\nDirection: {signal}"

@bot.message_handler(commands=['start', 'analyze'])
def send_analysis(message):
    try:
        df = fetch_data()
        result = analyze_market(df)
        bot.reply_to(message, f"📊 **Market Analysis:**\n\n{result}", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

# ৪. বট চালু করা
if __name__ == "__main__":
    # ওয়েবসাইটটি আলাদা থ্রেডে চালু হবে
    t = Thread(target=run_web)
    t.start()
    print("Bot is starting...")
    bot.infinity_polling()
