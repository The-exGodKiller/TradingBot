"""
Simplified Binance Futures Trading Bot (Testnet)

Features:
- Places MARKET and LIMIT orders on Binance Futures Testnet (USDT-M)
- Optional Stop-Limit order (implemented as STOP/STOP_MARKET variant)
- REST-based signed requests (no third-party lib required)
- CLI interface (argparse) with input validation
- Detailed logging of requests, responses, and errors to `bot.log`

How to use:
1. Register and activate a Binance Futures Testnet account and create API keys.
2. Run this script with --api-key and --api-secret or set environment variables BINANCE_API_KEY and BINANCE_API_SECRET.
3. Example:
   python simplified_binance_futures_bot.py market --symbol BTCUSDT --side BUY --quantity 0.001 --api-key YOUR_KEY --api-secret YOUR_SECRET

Note: This script uses the testnet base URL: https://testnet.binancefuture.com

"""

import argparse
import os
import time
import hmac
import hashlib
import logging
import requests
from urllib.parse import urlencode

# --- Configuration ---
TESTNET_BASE = "https://testnet.binancefuture.com"
API_ORDER_PATH = "/fapi/v1/order"
API_TIME_PATH = "/fapi/v1/time"
LOGFILE = "bot.log"

# --- Logging setup ---
logger = logging.getLogger("SimplifiedBinanceBot")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

fh = logging.FileHandler(LOGFILE)
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)

logger.addHandler(fh)
logger.addHandler(ch)


class BinanceFuturesRest:
    def __init__(self, api_key: str, api_secret: str, base_url: str = TESTNET_BASE):
        self.api_key = api_key
        self.api_secret = api_secret.encode('utf-8')
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            'X-MBX-APIKEY': self.api_key,
            'Content-Type': 'application/x-www-form-urlencoded'
        })

    def _get_timestamp(self):
        # Use server time to avoid invalid timestamp issues
        try:
            r = self.session.get(self.base + API_TIME_PATH, timeout=5)
            r.raise_for_status()
            server_time = r.json().get('serverTime')
            if server_time:
                return int(server_time)
        except Exception as e:
            logger.warning(f"Could not fetch server time: {e} — falling back to local time")
        return int(time.time() * 1000)

    def _sign(self, data: dict) -> str:
        query_string = urlencode(data, doseq=True)
        signature = hmac.new(self.api_secret, query_string.encode('utf-8'), hashlib.sha256).hexdigest()
        return signature

    def _send_signed(self, method: str, path: str, payload: dict):
        url = self.base + path
        payload['timestamp'] = self._get_timestamp()
        signature = self._sign(payload)
        payload['signature'] = signature
        body = urlencode(payload, doseq=True)

        logger.debug(f"REQUEST -> {method} {url} | body: {body}")
        try:
            if method.upper() == 'POST':
                r = self.session.post(url, data=body, timeout=10)
            elif method.upper() == 'DELETE':
                r = self.session.delete(url, data=body, timeout=10)
            else:
                r = self.session.get(url, params=payload, timeout=10)

            logger.debug(f"RESPONSE [{r.status_code}] -> {r.text}")
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as he:
            try:
                err = r.json()
            except Exception:
                err = r.text
            logger.error(f"HTTP error: {he} | response: {err}")
            raise
        except Exception as e:
            logger.error(f"Network/Error: {e}")
            raise

    # Public wrappers
    def place_market_order(self, symbol: str, side: str, quantity: float, reduceOnly: bool = False, timeInForce: str = None):
        payload = {
            'symbol': symbol,
            'side': side,
            'type': 'MARKET',
            'quantity': self._fmt_qty(quantity),
            'reduceOnly': str(reduceOnly).lower()
        }
        return self._send_signed('POST', API_ORDER_PATH, payload)

    def place_limit_order(self, symbol: str, side: str, quantity: float, price: float, timeInForce: str = 'GTC', reduceOnly: bool = False):
        payload = {
            'symbol': symbol,
            'side': side,
            'type': 'LIMIT',
            'timeInForce': timeInForce,
            'quantity': self._fmt_qty(quantity),
            'price': self._fmt_price(price),
            'reduceOnly': str(reduceOnly).lower()
        }
        return self._send_signed('POST', API_ORDER_PATH, payload)

    def place_stop_limit_order(self, symbol: str, side: str, quantity: float, stopPrice: float, price: float, timeInForce: str = 'GTC', reduceOnly: bool = False):
        # Implemented using STOP (STOP_MARKET / STOP_LOSS_LIMIT variants exist) for futures endpoint
        # We'll use STOP as "STOP" + LIMIT as type STOP with price & stopPrice where supported.
        payload = {
            'symbol': symbol,
            'side': side,
            'type': 'STOP',
            'quantity': self._fmt_qty(quantity),
            'stopPrice': self._fmt_price(stopPrice),
            'price': self._fmt_price(price),
            'timeInForce': timeInForce,
            'reduceOnly': str(reduceOnly).lower()
        }
        return self._send_signed('POST', API_ORDER_PATH, payload)

    @staticmethod
    def _fmt_qty(q):
        # Binance expects string numbers; CLI provides float — keep a reasonable precision
        return format(float(q), 'f')

    @staticmethod
    def _fmt_price(p):
        return format(float(p), 'f')


# --- CLI and Validation ---

def valid_side(s: str) -> str:
    s = s.upper()
    if s not in ('BUY', 'SELL'):
        raise argparse.ArgumentTypeError("side must be BUY or SELL")
    return s


def positive_number(x: str) -> float:
    try:
        v = float(x)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a number")
    if v <= 0:
        raise argparse.ArgumentTypeError("must be > 0")
    return v


def build_parser():
    p = argparse.ArgumentParser(description='Simplified Binance Futures Trading Bot (Testnet)')
    p.add_argument('--api-key', help='Binance API Key (or set BINANCE_API_KEY env var)')
    p.add_argument('--api-secret', help='Binance API Secret (or set BINANCE_API_SECRET env var)')

    sub = p.add_subparsers(dest='command', required=True, help='order commands')

    # Market
    mkt = sub.add_parser('market', help='Place a market order')
    mkt.add_argument('--symbol', required=True, help='Trading pair, e.g., BTCUSDT')
    mkt.add_argument('--side', required=True, type=valid_side, help='BUY or SELL')
    mkt.add_argument('--quantity', required=True, type=positive_number, help='Quantity in contract units')

    # Limit
    lim = sub.add_parser('limit', help='Place a limit order')
    lim.add_argument('--symbol', required=True)
    lim.add_argument('--side', required=True, type=valid_side)
    lim.add_argument('--quantity', required=True, type=positive_number)
    lim.add_argument('--price', required=True, type=positive_number)
    lim.add_argument('--time-in-force', default='GTC', choices=['GTC', 'IOC', 'FOK'])

    # Stop-Limit (bonus)
    stop = sub.add_parser('stop_limit', help='Place a stop-limit order (stopPrice + price)')
    stop.add_argument('--symbol', required=True)
    stop.add_argument('--side', required=True, type=valid_side)
    stop.add_argument('--quantity', required=True, type=positive_number)
    stop.add_argument('--stop-price', required=True, type=positive_number)
    stop.add_argument('--price', required=True, type=positive_number)
    stop.add_argument('--time-in-force', default='GTC', choices=['GTC', 'IOC', 'FOK'])

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    api_key = args.api_key or os.getenv('BINANCE_API_KEY')
    api_secret = args.api_secret or os.getenv('BINANCE_API_SECRET')
    if not api_key or not api_secret:
        logger.error('API credentials required via flags or environment variables')
        parser.print_help()
        return

    client = BinanceFuturesRest(api_key, api_secret)

    try:
        if args.command == 'market':
            logger.info(f"Placing MARKET {args.side} order for {args.symbol} qty={args.quantity}")
            resp = client.place_market_order(args.symbol.upper(), args.side.upper(), args.quantity)

        elif args.command == 'limit':
            logger.info(f"Placing LIMIT {args.side} order for {args.symbol} qty={args.quantity} price={args.price}")
            resp = client.place_limit_order(args.symbol.upper(), args.side.upper(), args.quantity, args.price, timeInForce=args.time_in_force)

        elif args.command == 'stop_limit':
            logger.info(f"Placing STOP-LIMIT {args.side} order for {args.symbol} qty={args.quantity} stopPrice={args.stop_price} price={args.price}")
            resp = client.place_stop_limit_order(args.symbol.upper(), args.side.upper(), args.quantity, args.stop_price, args.price, timeInForce=args.time_in_force)

        else:
            logger.error('Unknown command')
            return

        # Output order details and execution status
        logger.info('Order response:')
        logger.info(resp)
        print('\n--- ORDER RESULT ---')
        for k, v in resp.items():
            print(f"{k}: {v}")
        print('--------------------\n')

    except Exception as e:
        logger.exception(f"Failed to place order: {e}")


if __name__ == '__main__':
    main()
