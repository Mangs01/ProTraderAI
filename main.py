import os
print(os.getcwd())

from loguru import logger
from datetime import datetime, timedelta

from broker.angelone import AngelOneBroker
from core.indicators import Indicators

from strategy.ema_strategy import EMAStrategy
from execution.order_manager import OrderManager

from live.live_feed import LiveFeed
from paper.paper_engine import PaperEngine
from config.settings import *

def main():

    logger.info("========================================")
    logger.info("🚀 ProTraderAI X Started")
    logger.info("========================================")

    broker = AngelOneBroker()

    broker.login()
    
    order_manager = OrderManager(broker)
    paper = PaperEngine() 

    logger.info("Downloading Historical Data...")

    to_date = datetime.now()
    from_date = to_date - timedelta(days=30)

    candles = broker.get_historical_data(
        exchange=EXCHANGE,
        symboltoken=SYMBOL_TOKEN,
        interval=INTERVAL,
        fromdate=from_date.strftime("%Y-%m-%d %H:%M"),
        todate=to_date.strftime("%Y-%m-%d %H:%M")
    )

    feed = LiveFeed(
        broker.get_jwt_token(),
        API_KEY,
        CLIENT_CODE,
        broker.get_feed_token()
    )
    
    print("Live Feed Object Created Successfully")

    #feed.start()

    if not candles or candles.get("data") is None:
        logger.error("Historical Data Not Found")
        return

    df = Indicators.prepare_dataframe(candles["data"])

    df["EMA20"] = Indicators.ema(df, 20)
    df["EMA50"] = Indicators.ema(df, 50)
    df["RSI"] = Indicators.rsi(df)

    logger.success("Indicators Calculated")

    signal = EMAStrategy.signal(df)

    logger.info(f"Signal : {signal}")

    latest_price = df.iloc[-1]["close"]

    if signal == "BUY":

        stop_loss = latest_price - 5

        paper.buy(latest_price)

        order_manager.buy(
            latest_price,
            stop_loss
        )

    elif signal == "SELL":

        stop_loss = latest_price + 5

        paper.sell(latest_price)

        order_manager.sell(
            latest_price,
            stop_loss
        )

    else:

        paper.exit(latest_price)

    print(df.tail())


if __name__ == "__main__":
    main()