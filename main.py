from linecache import cache
import os
from unittest import result

import broker

print(os.getcwd())

from loguru import logger
from datetime import datetime, timedelta

from broker.angelone import AngelOneBroker
from core.indicators import Indicators

from strategy.strategy_manager import StrategyManager
from execution.order_manager import OrderManager

from live.live_feed import LiveFeed
from paper.paper_engine import PaperEngine

from backtest.backtest_runner import BacktestRunner
from config.settings import *

from data.historical_cache import HistoricalCache
from utils.time_utils import completed_session_range

def main():

    logger.info("========================================")
    logger.info("🚀 ProTraderAI X Started")
    logger.info("========================================")

    lookback_days = HISTORICAL_LOOKBACK_DAYS.get(INTERVAL, 90)
    if INTERVAL == "FIVE_MINUTE":
        from_date, to_date = completed_session_range(
            lookback_days=lookback_days,
        )
    else:
        to_date = datetime.now()
        from_date = to_date - timedelta(days=lookback_days)

    # Live feed remains disabled in backtest mode.

    cache = HistoricalCache(
        exchange=EXCHANGE,
        symboltoken=SYMBOL_TOKEN,
        interval=INTERVAL,
        cas_eligible=INSTRUMENT_IS_CAS_ENABLED,
    )
    broker = None
    downloaded = False
    cached_df = cache.load(
        requested_start=from_date,
        requested_end=to_date,
    )
    if cached_df is not None and not cached_df.empty:
        candles = {"data": cached_df.values.tolist()}
    else:
        broker = AngelOneBroker()
        broker.login()
        downloaded = True
        candles = broker.get_historical_data(
            exchange=EXCHANGE,
            symboltoken=SYMBOL_TOKEN,
            interval=INTERVAL,
            fromdate=from_date.strftime("%Y-%m-%d %H:%M"),
            todate=to_date.strftime("%Y-%m-%d %H:%M"),
            chunk_days=HISTORICAL_CHUNK_DAYS.get(INTERVAL, 90),
            pace_seconds=HISTORICAL_REQUEST_PACE_SECONDS,
            max_retries=HISTORICAL_MAX_RETRIES,
            retry_backoff_seconds=HISTORICAL_RETRY_BACKOFF_SECONDS,
            cas_eligible=INSTRUMENT_IS_CAS_ENABLED,
        )
    if downloaded and candles and candles.get("data"):
        cache.save(
            candles["data"],
            requested_start=from_date,
            requested_end=to_date,
        )
    if not candles or candles.get("data") is None:
        if broker is not None and broker.last_download_diagnostics is not None:
            logger.error(
                f"Historical download diagnostics: "
                f"{broker.last_download_diagnostics}"
            )
        logger.error("Historical Data Not Found")
        return

    # ----------------------------------------
    # BACKTEST MODE
    # ----------------------------------------
    logger.info(
        f"Historical Candles Received : {len(candles['data'])}"
    )

    logger.info(
        f"First Candle : {candles['data'][0]}"
    )

    logger.info(
        f"Last Candle : {candles['data'][-1]}"
    )

    backtest_runner = BacktestRunner(
        Indicators.prepare_dataframe(candles["data"]),
        interval=INTERVAL,
        cas_eligible=INSTRUMENT_IS_CAS_ENABLED,
    )

    result = backtest_runner.run()

    logger.info("========================================")
    logger.info("📊 BACKTEST RESULT")
    logger.info("========================================")

    logger.info(f"Total Trades    : {result['total_trades']}")
    logger.info(f"Winning Trades  : {result['winning_trades']}")
    logger.info(f"Losing Trades   : {result['losing_trades']}")
    logger.info(f"Win Rate        : {result['win_rate']}%")
    logger.info(f"Net P&L         : ₹{result['net_pnl']}")
    logger.info(f"Final Capital   : ₹{result['final_capital']}")
    logger.info(
        f"Equity Curve Points : {len(result['equity_curve'])}"
    )

    logger.info(
        f"Breakeven Trades: {result['breakeven_trades']}"
    )

    logger.info(
        f"Gross Profit    : ₹{result['gross_profit']}"
    )

    logger.info(
        f"Gross Loss      : ₹{result['gross_loss']}"
    )

    logger.info(
        f"Profit Factor   : {result['profit_factor']}"
    )

    logger.info(
        f"Average Win     : ₹{result['average_win']}"
    )

    logger.info(
        f"Average Loss    : ₹{result['average_loss']}"
    )

    logger.info(
        f"Gross Net P&L    : ₹{result['gross_net_pnl']}"
    )

    logger.info(
        f"Total Charges    : ₹{result['total_charges']}"
    )

    logger.info(
        f"Net P&L          : ₹{result['net_pnl']}"
    )

    logger.info(
        f"Max Drawdown     : ₹{result['max_drawdown']}"
    )

    logger.info(
        f"Max DD %         : {result['max_drawdown_percent']}%"
    )

    # ----------------------------------------
    # TRADE-BY-TRADE REPORT
    # ----------------------------------------

    logger.info("========================================")
    logger.info("📋 TRADE-BY-TRADE REPORT")
    logger.info("========================================")

    for index, trade in enumerate(
        backtest_runner.engine.trades,
        start=1
    ):

        logger.info(
            f"Trade {index:02d} | "
            f"{trade['side']} | "
            f"Entry={trade['entry']:.2f} | "
            f"Exit={trade['exit']:.2f} | "
            f"Qty={trade['quantity']} | "
            f"Gross=₹{trade['gross_pnl']:.2f} | "
            f"Charges=₹{trade['charges']:.2f} | "
            f"Net=₹{trade['pnl']:.2f} | "
            f"Reason={trade['reason']}"
        )

    logger.info("========================================")

    return

    df = Indicators.prepare_dataframe(candles["data"])

    df["EMA20"] = Indicators.ema(df, 20)
    df["EMA50"] = Indicators.ema(df, 50)
    df["RSI"] = Indicators.rsi(df)

    df["VWAP"] = Indicators.vwap(df)
    df["VolumeSMA"] = Indicators.volume_sma(df, 20)
    df["ATR"] = Indicators.atr(df, 14)

    logger.success("Indicators Calculated")

    strategy_manager = StrategyManager()

    signal = strategy_manager.get_signal(df)

    print(df[["close", "ATR"]].tail())

    logger.info(f"Signal : {signal}")

    latest_price = df.iloc[-1]["close"]
    atr = df.iloc[-1]["ATR"]

    if signal == "BUY":

        stop_loss = latest_price - (1.5 * atr)
        target = latest_price + (2 * atr)

        quantity = order_manager.buy(
            latest_price,
            stop_loss,
            target
        )

        if quantity:

            paper.buy(
                latest_price,
                quantity
            )

    elif signal == "SELL":

        stop_loss = latest_price + (1.5 * atr)
        target = latest_price - (2 * atr)

        quantity = order_manager.sell(
            latest_price,
            stop_loss,
            target
        )

        if quantity:
            paper.sell(
                latest_price,
                quantity
            )

    else:

        paper.exit(latest_price)

    # Trade Monitoring
    status = order_manager.monitor_trade(latest_price)

    logger.info(f"Trade Status : {status}")

    print(df.tail())


if __name__ == "__main__":
    main()
