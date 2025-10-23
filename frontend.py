import streamlit as st
from simplified_binance_futures_bot import BinanceFuturesRest
import os

st.set_page_config(page_title="Trading Bot UI", layout="centered")

st.title("💹 Simplified Binance Futures Trading Bot (Testnet)")

api_key = st.text_input("Enter API Key", type="password")
api_secret = st.text_input("Enter API Secret", type="password")
symbol = st.text_input("Symbol", "BTCUSDT")
side = st.selectbox("Order Side", ["BUY", "SELL"])
order_type = st.selectbox("Order Type", ["MARKET", "LIMIT", "STOP-LIMIT"])
quantity = st.number_input("Quantity", min_value=0.0001, value=0.001, step=0.0001)

price = None
stop_price = None

if order_type in ["LIMIT", "STOP-LIMIT"]:
    price = st.number_input("Price", min_value=0.0, value=69000.0, step=100.0)

if order_type == "STOP-LIMIT":
    stop_price = st.number_input("Stop Price", min_value=0.0, value=68800.0, step=100.0)

if st.button("📈 Place Order"):
    if not api_key or not api_secret:
        st.error("Please enter both API Key and Secret.")
    else:
        bot = BinanceFuturesRest(api_key, api_secret)
        try:
            if order_type == "MARKET":
                resp = bot.place_market_order(symbol, side, quantity)
            elif order_type == "LIMIT":
                resp = bot.place_limit_order(symbol, side, quantity, price)
            else:
                resp = bot.place_stop_limit_order(symbol, side, quantity, stop_price, price)

            st.success("✅ Order Placed Successfully!")
            st.json(resp)
        except Exception as e:
            st.error(f"❌ Error placing order: {e}")
