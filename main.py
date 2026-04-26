import os
import time
import pytz
import ccxt
import pandas as pd
import ta
import telebot
from threading import Thread
from flask import Flask
from datetime import datetime


# ১. টেলিগ্রাম বট টোকেন (আপনার টোকেনটি এখানে বসান)
API_TOKEN = '8537303678:AAFVsbISMZZkfCMlqcJ9EQScz5OjbIwrXvs'
bot = telebot.TeleBot(API_TOKEN)

# ২. ওয়েব সার্ভার (Render এর জন্য)
app = Flask('')
@app.route('/')
def home(): return "Pro Trader Bot is Active!"

def run_web():
    # Render নিজে থেকে যে পোর্ট অ্যাসাইন করে সেটা আগে চেক করবে, না পেলে ১০০০০ নিবে
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)


def fetch_market_data(symbol):
    symbol = symbol.upper()
    # যদি কেউ শুধু EUR লেখে, তবে তাকে EUR/USDT তে রূপান্তর করবে
    if "/" not in symbol:
        symbol = f"{symbol}/USDT"
    
    # বিন্যান্স সাধারণত ফরেক্স পেয়ার সাপোর্ট করে
    exchange = ccxt.binance({'enableRateLimit': True})
    
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=300)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return df, symbol
    except Exception as e:
        # যদি বিন্যান্সে না পায়, তবে অন্য এক্সচেঞ্জে ট্রাই করবে
        print(f"Error: {e}")
        raise Exception("পেয়ারটি খুঁজে পাওয়া যায়নি।")


# ৪. সরাসরি ট্রেডিং অ্যাকশন লজিক
def analyze_market(df):
    # ইন্ডিকেটর ক্যালকুলেশন
    bb = ta.volatility.BollingerBands(close=df["close"], window=20, window_dev=2)
    df['bb_high'], df['bb_low'] = bb.bollinger_hband(), bb.bollinger_lband()
    df['rsi'] = ta.momentum.rsi(df["close"], window=14)
    df['ema_50'] = ta.trend.ema_indicator(df["close"], window=50)
    adx_ind = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14)
    df['adx'] = adx_ind.adx()
    stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'], window=14)
    df['stoch_k'] = stoch.stoch()

    last = df.iloc[-1]
    close, rsi, adx = last['close'], last['rsi'], last['adx']
    bb_high, bb_low = last['bb_high'], last['bb_low']
    stoch_k, ema_50 = last['stoch_k'], last['ema_50']

    # --- সিগন্যাল লজিক (কখন কোন এন্ট্রি নিবেন) ---
    action = "⏳ WAIT (NO ENTRY)"
    entry = close
    target = "N/A"
    sl = "N/A"
    advice = "মার্কেট এখন নিউট্রাল জোনে আছে। সঠিক সময়ের জন্য অপেক্ষা করুন।"

    # ১. ক্লিয়ার বাই (Buy/Long) এন্ট্রি
    if close <= (bb_low * 1.002) and rsi < 35 and stoch_k < 20:
        action = "🟢 BUY / LONG"
        target = round(close * 1.015, 4) # ১.৫% লাভ
        sl = round(close * 0.992, 4)     # ০.৮% স্টপ লস
        advice = "মার্কেট সাপোর্ট জোনে আছে। এখান থেকে দাম বাড়ার সম্ভাবনা বেশি।"

    # ২. ক্লিয়ার সেল (Sell/Short) এন্ট্রি
    elif close >= (bb_high * 0.998) and rsi > 65 and stoch_k > 80:
        action = "🔴 SELL / SHORT"
        target = round(close * 0.985, 4)
        sl = round(close * 1.008, 4)
        advice = "মার্কেট রেজিস্ট্যান্স জোনে আছে। এখান থেকে দাম কমার সম্ভাবনা বেশি।"
    
    # ৩. ট্রেন্ড ফলোয়িং বাই (যদি ট্রেন্ড খুব স্ট্রং থাকে)
    elif adx > 25 and close > ema_50 and rsi < 60:
        action = "📈 TREND BUY"
        target = round(close * 1.01, 4)
        sl = round(ema_50 * 0.995, 4)
        advice = "মার্কেট একটি শক্তিশালী আপট্রেন্ডে আছে। ট্রেন্ডের সাথে বাই করা নিরাপদ।"

    return {
        "price": close, "action": action, "target": target, 
        "sl": sl, "advice": advice, "rsi": round(rsi, 1), "adx": round(adx, 1)
    }

# ৫. কমান্ড হ্যান্ডলার
@bot.message_handler(commands=['analyze'])
def get_analysis(message):
    try:
        args = message.text.split()
        target_coin = args[1] if len(args) > 1 else "BTC"
        
        df, final_symbol = fetch_market_data(target_coin)
        data = analyze_market(df)
        
        # বাংলাদেশ সময় সেট করা
        bd_timezone = pytz.timezone('Asia/Dhaka')
        bd_time = datetime.now(bd_timezone).strftime('%I:%M %p, %d %b %Y')
        
        response = (
            f"📊 **{final_symbol} Signal Report**\n"
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
        bot.send_message(message.chat.id, "❌ ডাটা পেতে সমস্যা হয়েছে। যেমন: `/analyze eth` লিখে চেষ্টা করুন।")

# ৬. রান করার প্রসেস
if __name__ == "__main__":
    Thread(target=run_web).start()
    time.sleep(2)
    bot.remove_webhook()
    print("Bot is Live with BD Time and Direct Signals...")
    bot.infinity_polling(skip_pending=True)
