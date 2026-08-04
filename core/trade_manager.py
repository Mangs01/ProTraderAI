from loguru import logger


class TradeManager:

    def __init__(self):

        logger.info("Trade Manager Loaded")

        self.trade_active = False

    def start_trade(self):

        self.trade_active = True

        logger.success("Trade Started")

    def end_trade(self):

        self.trade_active = False

        logger.warning("Trade Closed")

    def is_active(self):

        return self.trade_active