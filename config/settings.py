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

INTERVAL = "ONE_DAY"

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