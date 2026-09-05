from loguru import logger

from config.settings import STRATEGY

from strategy.ema_strategy import EMAStrategy


class StrategyManager:

    def __init__(self):

        logger.info(f"Strategy Selected : {STRATEGY}")

    def required_indicators(self):

        if STRATEGY == "EMA":

            return EMAStrategy.REQUIRED_INDICATORS

        return ()

    def get_signal(self, df):

        if STRATEGY == "EMA":

            return EMAStrategy.signal(df)

        logger.warning("Unknown Strategy")

        return "HOLD"