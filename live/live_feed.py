from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from loguru import logger

from utils.tick_parser import TickParser
from data.live_cache import LiveCache
from live.candle_builder import CandleBuilder


class LiveFeed:

    def __init__(
        self,
        jwt_token,
        api_key,
        client_code,
        feed_token
    ):

        self.cache = LiveCache()

        self.builder = CandleBuilder()

        self.sws = SmartWebSocketV2(
            jwt_token,
            api_key,
            client_code,
            feed_token
        )

    # ------------------- CALLBACKS ------------------- #

    def on_open(self, wsapp):

        logger.success("Live Feed Connected")

        token_list = [
            {
                "exchangeType": 1,
                "tokens": ["3045"]      # SBIN
            }
        ]

        self.sws.subscribe(
            correlation_id="ProTraderAI",
            mode=1,
            token_list=token_list
        )

        logger.success("Subscribed : SBIN")

    def on_data(self, wsapp, message):

        tick = TickParser.parse(message)

        self.cache.update(
            tick["token"],
            tick
        )

        candle = self.builder.update(tick["ltp"])
        
        if candle:
            logger.success(f"Completed Candle : {candle}")
        
        print("\n===================================")
        print("TOKEN :", tick["token"])
        print("LTP   :", tick["ltp"])
        print("TIME  :", tick["time"])
        print("===================================\n")

    def on_error(self, wsapp, error):

        logger.error(error)

    def on_close(self, wsapp):

        logger.warning("Live Feed Closed")

    # ------------------- START ------------------- #

    def start(self):

        self.sws.on_open = self.on_open
        self.sws.on_data = self.on_data
        self.sws.on_error = self.on_error
        self.sws.on_close = self.on_close

        self.sws.connect()