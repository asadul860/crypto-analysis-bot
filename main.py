import ccxt
import pandas as pd
import ta
import telebot
import os
from threading import Thread
from flask import Flask

# ১. টেলিগ্রাম বট টোকেন (আপনার টোকেনটি এখানে বসান)
API_TOKEN = '8537303678:AAFVsbISMZZkfCMlqcJ9EQScz5OjbIwrXvs'
bot = telebot.TeleBot(API_TOKEN)

# ২. Render-এর জন্য ছোট ওয়েব সার্ভার
app = Flask('')

@app.route('/')
def home():
    return "Market Bot is Live!"

def run_web():
    # Render সাধারণত ৮কোটি৮০ বা অন্য পোর্টে রান করতে বলে
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ৩. মার্কেট এনালাইসিস ফাংশন
def analyze_market(df):
    # বোলিঙ্গার ব্যান্ডস ক্যালকুলেশন (Period 20, Std Dev 2)
    indicator_bb = ta.volatility.BollingerBands(close=df["close"], window=20, window_dev=2)
    
    df['bb_high'] = indicator_bb.bollinger_hband()
    df['bb_low'] = indicator_bb.bollinger_lband()
    df['bb_mid'] = indicator_bb.bollinger_mavg()
    
    last_row = df.iloc[-1]
    close = last_row['close']
    upper = last_row['bb_high']
    lower = last_row['bb_low']

    if close <= lower:
        signal = "🚀 **Strong BUY** (Price at Lower Band)"
    elif close >= upper:
        signal = "🔻 **Strong SELL** (Price at Upper Band)"
    elif close > last_row['bb_mid']:
        signal = "📈 **Bullish Trend** (Above Middle Band)"
    else:
        signal = "📉 **Bearish Trend** (Below Middle Band)"

    return f"💰 **Price:** {close}\n🔴 **Upper Band:** {upper:.2f}\n🟢 **Lower Band:** {lower:.2f}\n\n🎯 **Direction:** {signal}"

# ৪. ডাটা ফেচ করার ফাংশন (Binance + KuCoin Fallback)
def fetch_market_data(symbol='BTC/USDT'):
    try:
        # প্রথমে বিন্যান্স চেষ্টা করবে
        exchange = ccxt.binance({'enableRateLimit': True})
        bars = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
    except Exception as e:
        # বিন্যান্স ব্লক থাকলে কু-কয়েন ব্যবহার করবে
        print(f"Binance restricted, trying KuCoin... Error: {e}")
        exchange = ccxt.kucoin({'enableRateLimit': True})
        bars = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
    
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    return df

# ৫. টেলিগ্রাম কমান্ড হ্যান্ডলার
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "স্বাগতম! মার্কেট এনালাইসিস দেখতে `/analyze` লিখে মেসেজ দিন।")

@bot.message_handler(commands=['analyze'])
def send_analysis(message):
    bot.send_message(message.chat.id, "⏳ মার্কেট ডাটা এনালাইসিস করা হচ্ছে...")
    try:
        df = fetch_market_data('BTC/USDT')
        result = analyze_market(df)
        bot.send_message(message.chat.id, f"📊 **BTC/USDT Analysis (1H)**\n\n{result}", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ এরর: ডাটা পাওয়া যায়নি। বিস্তারিত: {str(e)}")

# ৬. মেইন এক্সিকিউশন
if __name__ == "__main__":
    # ওয়েব সার্ভার শুরু (Render-এর জন্য)
    t = Thread(target=run_web)
    t.start()
    
    print("Bot is polling...")
    # বট পোলিং শুরু
    bot.infinity_polling()
