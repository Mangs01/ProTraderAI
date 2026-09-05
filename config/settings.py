from dotenv import load_dotenv
import os

# ======================================
# Load Environment Variables
# ======================================

load_dotenv()

# ======================================
# Broker Credentials
# (Read from .env file)
# ======================================

API_KEY = os.getenv("API_KEY")

CLIENT_CODE = os.getenv("CLIENT_CODE")

MPIN = os.getenv("MPIN")

TOTP_SECRET = os.getenv("TOTP_SECRET")

# ======================================
# Trading Settings
# ======================================

EXCHANGE = "NSE"

SYMBOL = "SBIN-EQ"

SYMBOL_TOKEN = "3045"

INTERVAL = "FIVE_MINUTE"

QUANTITY = 1

# ======================================
# Risk Management
# ======================================

MAX_DAILY_LOSS = 2000

MAX_TRADE_PER_DAY = 5

RISK_PER_TRADE = 1.0

# ======================================
# Paper Trading
# ======================================

PAPER_BALANCE = 100000

# ======================================
# Logging
# ======================================

LOG_LEVEL = "INFO"

# ---------------------------------------
# Strategy
# ---------------------------------------

STRATEGY = "EMA"
# STRATEGY = "VWAP"
# STRATEGY = "ORB"
# STRATEGY = "SUPERTREND"
# ---------------------------------------
# Historical Data
# ---------------------------------------

HISTORICAL_LOOKBACK_DAYS = {
    "ONE_DAY": 365,
    "FIVE_MINUTE": 30,
}

HISTORICAL_CHUNK_DAYS = {
    "ONE_DAY": 365,
    "FIVE_MINUTE": 30,
}

HISTORICAL_REQUEST_PACE_SECONDS = 0.5
HISTORICAL_MAX_RETRIES = 3
HISTORICAL_RETRY_BACKOFF_SECONDS = 5.0
# ---------------------------------------
# Backtest Trading Session
# ---------------------------------------

TRADING_TIMEZONE = "Asia/Kolkata"
INTRADAY_INTERVALS = {
    "ONE_MINUTE",
    "THREE_MINUTE",
    "FIVE_MINUTE",
    "TEN_MINUTE",
    "FIFTEEN_MINUTE",
    "THIRTY_MINUTE",
    "ONE_HOUR",
}
NSE_SESSION_START = "09:15"
NSE_SESSION_END = "15:30"
NSE_FINAL_BAR_START = "15:25"
NSE_LAST_ENTRY_CUTOFF = "15:15"
FIVE_MINUTE_BAR_MINUTES = 5
INCOMPLETE_SESSION_POLICY = "REJECT"

# NSE Closing Auction Session (CAS) Phase 1. Eligibility must be confirmed
# from SmartAPI instrument-master is_cas_enabled; explicit configuration keeps
# offline backtests independent from network access.
NSE_CAS_EFFECTIVE_DATE = "2026-08-03"
NSE_CAS_CONTINUOUS_FINAL_BAR_START = "15:10"
NSE_CAS_ENTRY_CUTOFF = "15:10"
NSE_CAS_PERIOD_BAR_STARTS = ("15:15", "15:20", "15:25")
FIVE_MINUTE_SESSION_POLICY_VERSION = 2
INSTRUMENT_IS_CAS_ENABLED = True

# ---------------------------------------
# Indicator Periods
# ---------------------------------------

EMA_FAST_PERIOD = 20
EMA_SLOW_PERIOD = 50
RSI_PERIOD = 14
ATR_PERIOD = 14
VOLUME_SMA_PERIOD = 20

# Deterministic adverse backtest execution slippage.
BACKTEST_SLIPPAGE_BPS = 5

# NSE cash-equity intraday charges (verified as of September 2026).
BROKERAGE_RATE = 0.001
BROKERAGE_MIN_PER_ORDER = 5.0
BROKERAGE_MAX_PER_ORDER = 20.0
NSE_TRANSACTION_RATE = 0.000030699
STT_SELL_RATE = 0.00025
STAMP_DUTY_BUY_RATE = 0.00003
SEBI_RATE = 0.000001
IPFT_RATE = 0.000000001
GST_RATE = 0.18
