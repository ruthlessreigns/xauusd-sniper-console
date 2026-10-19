import io
import math
import requests
import datetime
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# MetaTrader 5 Safety Import for Cloud Deployment
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
SYMBOL = "XAUUSD"
ACCOUNT_BALANCE = 10000.0
RISK_PERCENT = 1.0

st.set_page_config(page_title="XAUUSD Shared Sniper Console", page_icon="⚡", layout="wide")

st.title("⚡ XAUUSD Institutional Sniper Signal Console")
st.write("Fetch live market data from your local MetaTrader 5 and dispatch high-confluence signals directly to your custom Telegram channel.")

# ==========================================
# 2. SIDEBAR - USER TELEGRAM CREDENTIALS
# ==========================================
st.sidebar.header("🔑 Your Telegram Settings")
st.sidebar.write("Provide your Telegram Bot parameters below:")

telegram_bot_token = st.sidebar.text_input("Telegram Bot Token", value="", type="password", help="Enter your Telegram Bot Token")
telegram_chat_id = st.sidebar.text_input("Telegram Chat ID", value="", help="Enter your Telegram Chat ID")

if not telegram_bot_token or not telegram_chat_id:
    st.sidebar.warning("⚠️ Enter a valid Bot Token and Chat ID to enable signal dispatching.")

# ==========================================
# 3. GANN & TELEGRAM ENGINE
# ==========================================
def calculate_gannzilla_levels(price, is_buy=True):
    sqrt_p = math.sqrt(price)
    if is_buy:
        gann_90 = round(math.pow(sqrt_p - 0.5, 2), 2)
        gann_180 = round(math.pow(sqrt_p + 1.0, 2), 2)
        gann_360 = round(math.pow(sqrt_p + 2.0, 2), 2)
    else:
        gann_90 = round(math.pow(sqrt_p + 0.5, 2), 2)
        gann_180 = round(math.pow(sqrt_p - 1.0, 2), 2)
        gann_360 = round(math.pow(sqrt_p - 2.0, 2), 2)
    return gann_90, gann_180, gann_360

def send_telegram_signal(token, chat_id, msg_text, chart_bytes=None):
    if not token or not chat_id:
        st.error("❌ Telegram Bot Token or Chat ID is missing!")
        return False

    url_text = f"https://api.telegram.org/bot{token}/sendMessage"
    reply_markup = {
        "inline_keyboard": [
            [{"text": "⚡ EXECUTE SNIPER TRADE", "callback_data": "exec_sniper"}, {"text": "❌ IGNORE", "callback_data": "ignore_trade"}],
            [{"text": "🛡️ MOVE SL TO BE", "callback_data": "sl_be"}, {"text": "📊 CLOSE 50% PARTIALS", "callback_data": "close_partial"}]
        ]
    }
    
    try:
        res = requests.post(url_text, json={"chat_id": chat_id, "text": msg_text, "parse_mode": "HTML", "reply_markup": reply_markup})
        if res.status_code != 200:
            st.error(f"❌ Failed to dispatch message to Telegram! Response: {res.text}")
            return False

        if chart_bytes:
            url_photo = f"https://api.telegram.org/bot{token}/sendPhoto"
            files = {'photo': ('chart.png', chart_bytes, 'image/png')}
            requests.post(url_photo, data={'chat_id': chat_id, 'caption': "📈 Precision Matrix Visual Chart", 'parse_mode': 'HTML'}, files=files)
            
        return True
    except Exception as e:
        st.error(f"[ERROR]: {e}")
        return False

def get_rates(symbol, timeframe, count=50):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

# ==========================================
# 4. STEP 1: FETCH DATA FROM USER'S MT5
# ==========================================
def fetch_data_from_mt5():
    if not MT5_AVAILABLE:
        st.error("❌ MetaTrader 5 is only supported on local Windows desktop environments. Please run this app locally on your PC.")
        return None

    df_h4 = get_rates(SYMBOL, mt5.TIMEFRAME_H4, 50)
    df_h1 = get_rates(SYMBOL, mt5.TIMEFRAME_H1, 50)
    df_m15 = get_rates(SYMBOL, mt5.TIMEFRAME_M15, 50)
    df_m5 = get_rates(SYMBOL, mt5.TIMEFRAME_M5, 50)

    if df_h4.empty or df_h1.empty or df_m15.empty or df_m5.empty:
        st.error("❌ Unable to retrieve chart data from MT5. Ensure XAUUSD is active in Market Watch.")
        mt5.shutdown()
        return None

    current_price = round(df_m5.iloc[-1]['close'], 2)
    h4_trend = "BULLISH" if df_h4.iloc[-1]['close'] > df_h4.iloc[-10]['close'] else "BEARISH"
    h1_high = round(df_h1['high'].max(), 2)
    h1_low = round(df_h1['low'].min(), 2)
    h1_equilibrium = round((h1_high + h1_low) / 2.0, 2)

    m15_prev = df_m15.iloc[-2]
    m15_ob_mid = round((m15_prev['high'] + m15_prev['low']) / 2.0, 2)

    m5_last = df_m5.iloc[-1]
    m5_high = round(m5_last['high'], 2)
    m5_low = round(m5_last['low'], 2)
    total_len = m5_last['high'] - m5_last['low']

    now = datetime.datetime.now().time()
    if datetime.time(6, 0) <= now <= datetime.time(10, 0):
        session = "Asian Kill Zone 🌏"
    elif datetime.time(11, 0) <= now <= datetime.time(16, 0):
        session = "London Kill Zone 🇬🇧"
    elif datetime.time(17, 30) <= now <= datetime.time(22, 0):
        session = "New York Kill Zone 🇺🇸"
    else:
        session = "Off-Session Window ⚠️"

    avg_vol = df_m5['tick_volume'].tail(20).mean()
    vol_spike = m5_last['tick_volume'] > (avg_vol * 1.1)

    buy_wick = min(m5_last['open'], m5_last['close']) - m5_last['low']
    sell_wick = m5_last['high'] - max(m5_last['open'], m5_last['close'])
    
    buy_sweep = int(round((buy_wick / total_len) * 100)) if total_len > 0 else 0
    sell_sweep = int(round((sell_wick / total_len) * 100)) if total_len > 0 else 0

    mt5.shutdown()

    return {
        "current_price": current_price,
        "h4_trend": h4_trend,
        "h1_high": h1_high,
        "h1_low": h1_low,
        "h1_equilibrium": h1_equilibrium,
        "m15_ob_mid": m15_ob_mid,
        "m5_high": m5_high,
        "m5_low": m5_low,
        "buy_sweep": buy_sweep,
        "sell_sweep": sell_sweep,
        "vol_spike": vol_spike,
        "session": session,
        "m5_last": m5_last
    }

# ==========================================
# 5. STREAMLIT INTERFACE
# ==========================================
st.markdown("### 📡 Step 1: Fetch Market Data from MT5")

if st.button("📥 FETCH LIVE DATA FROM MT5", use_container_width=True, type="primary"):
    with st.spinner("Retrieving live market metrics from your MT5 terminal..."):
        data = fetch_data_from_mt5()
        if data:
            st.session_state['mt5_data'] = data
            st.success("✅ Latest market metrics successfully extracted from MT5!")

if 'mt5_data' in st.session_state:
    d = st.session_state['mt5_data']
    
    st.markdown("---")
    st.markdown("### 📊 Extracted Market Data Summary:")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Price", f"${d['current_price']}")
    col2.metric("H4 Macro Trend", d['h4_trend'])
    col3.metric("H1 Equilibrium", f"${d['h1_equilibrium']}")
    col4.metric("Active Session", d['session'])

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("M15 Order Block Mean", f"${d['m15_ob_mid']}")
    col6.metric("M5 Candle High / Low", f"${d['m5_high']} / ${d['m5_low']}")
    col7.metric("Buy / Sell True Sweep", f"{d['buy_sweep']}% / {d['sell_sweep']}%")
    col8.metric("Volume Spike", "Confirmed (>110%)" if d['vol_spike'] else "Normal")

    st.markdown("---")
    st.markdown("### 🚀 Step 2: Calculate & Dispatch Telegram Signal")

    if st.button("⚙️ CALCULATE & TRIGGER TELEGRAM SIGNAL", use_container_width=True, type="secondary"):
        if not telegram_bot_token or not telegram_chat_id:
            st.error("❌ Please configure your Telegram Bot Token and Chat ID in the sidebar first!")
        else:
            with st.spinner("Processing algorithmic matrix and evaluating setup probability..."):
                current_price = d['current_price']
                h4_trend = d['h4_trend']
                h1_equilibrium = d['h1_equilibrium']
                m15_ob_mid = d['m15_ob_mid']
                m5_last = d['m5_last']
                vol_spike = d['vol_spike']
                session = d['session']

                decision = "NO TRADE"
                is_buy = False

                if h4_trend == "BULLISH" and current_price < h1_equilibrium:
                    gann_90, gann_180, gann_360 = calculate_gannzilla_levels(current_price, is_buy=True)
                    gann_confluence = abs(m15_ob_mid - gann_90) <= (current_price * 0.005)
                    sweep_ratio = d['buy_sweep']

                    if gann_confluence and (sweep_ratio >= 65 or vol_spike):
                        decision = "BUY LIMIT"
                        is_buy = True

                elif h4_trend == "BEARISH" and current_price > h1_equilibrium:
                    gann_90, gann_180, gann_360 = calculate_gannzilla_levels(current_price, is_buy=False)
                    gann_confluence = abs(m15_ob_mid - gann_90) <= (current_price * 0.005)
                    sweep_ratio = d['sell_sweep']

                    if gann_confluence and (sweep_ratio >= 65 or vol_spike):
                        decision = "SELL LIMIT"
                        is_buy = False

                date_str = datetime.datetime.now().strftime("%d %B, %I:%M %p")

                if decision == "NO TRADE":
                    st.warning(f"⚠️ **NO TRADE ZONE** - High probability confluence rules not fully met. (Price: ${current_price})")
                    msg = f"""
⚪ <b>XAUUSD ANALYSIS RESULT: NO TRADE</b>
==================================
<b>Current Price:</b> <code>${current_price}</code>
<b>H4 Trend:</b> <code>{h4_trend}</code>
<b>Active Session:</b> {session}
<b>Status:</b> Market is out of strict confluence alignment.
==================================
<b>Time:</b> {date_str}
"""
                    if send_telegram_signal(telegram_bot_token, telegram_chat_id, msg):
                        st.info("📲 'NO TRADE' status update dispatched to your Telegram.")

                else:
                    st.success(f"🎯 **HIGH PROBABILITY SIGNAL GENERATED: {decision}**")
                    
                    if is_buy:
                        entry_price = round(current_price, 2)
                        stop_loss = round(m5_last['low'] - 1.5, 2)
                        tp1 = round(gann_180, 2)
                        tp2 = round(gann_360, 2)
                    else:
                        entry_price = round(current_price, 2)
                        stop_loss = round(m5_last['high'] + 1.5, 2)
                        tp1 = round(gann_180, 2)
                        tp2 = round(gann_360, 2)

                    dist = abs(entry_price - stop_loss)
                    risk_amount = ACCOUNT_BALANCE * (RISK_PERCENT / 100.0)
                    lot_size = round(risk_amount / (dist * 100), 2) if dist > 0 else 0.10
                    rrr = round(abs(tp2 - entry_price) / dist, 2) if dist > 0 else 0

                    fig, ax = plt.subplots(figsize=(8, 4), dpi=150)
                    plt.style.use('dark_background')
                    ax.axhline(y=entry_price, color='#e2a200', linestyle='--', label=f'Entry: ${entry_price}')
                    ax.axhline(y=gann_90, color='#ff00ff', linestyle=':', label=f'Gann 90°: ${gann_90}')
                    ax.axhline(y=stop_loss, color='#ff3333', linestyle='-', label=f'SL: ${stop_loss}')
                    ax.axhline(y=tp1, color='#00ff66', linestyle=':', label=f'Gann 180° TP1: ${tp1}')
                    ax.axhline(y=tp2, color='#00cc44', linestyle='-', label=f'Gann 360° TP2: ${tp2}')
                    ax.set_title(f"Custom Telegram Signal ({decision})", color='white')
                    ax.legend(loc='upper left', fontsize=8)
                    plt.tight_layout()

                    buf = io.BytesIO()
                    plt.savefig(buf, format='png')
                    buf.seek(0)
                    plt.close()

                    header_icon = "🟢" if is_buy else "🔴"
                    msg = f"""
{header_icon} <b>XAUUSD {decision} SNIPER SIGNAL</b>
==================================
<b>Session:</b> {session}
<b>Current Price:</b> <code>${current_price}</code>
<b>Sniper Entry:</b> <code>${entry_price}</code>
<b>Gann Hexagon 90°:</b> <code>${gann_90}</code>
<b>True Sweep Ratio:</b> <code>{sweep_ratio}%</code>
<b>Stop Loss (SL):</b> <code>${stop_loss}</code>
<b>Take Profit 1 (Gann 180°):</b> <code>${tp1}</code>
<b>Take Profit 2 (Gann 360°):</b> <code>${tp2}</code>
<b>Risk-to-Reward:</b> <code>1 : {rrr}</code>

📊 <b>Confluence Checklist:</b>
• HTF Trend ({h4_trend}): Verified
• Zone: {"Discount Zone" if is_buy else "Premium Zone"}
• Volume Spike: {"Confirmed (>110%)" if vol_spike else "Standard Volume"}
• Gann Matrix: 90° Reversal Aligned

💼 <b>Risk Sizing (1% Risk):</b>
• Recommended Lot Size: <code>{lot_size} Lots</code>
==================================
<b>Time:</b> {date_str}
"""
                    if send_telegram_signal(telegram_bot_token, telegram_chat_id, msg, buf.getvalue()):
                        st.success("🎯 Professional sniper signal with visual chart dispatched successfully to your Telegram channel!")
