from loguru import logger


class Engine:

    def __init__(
        self,
        broker,
        strategy,
        paper,
        risk,
        cache,
        candle_builder
    ):

        self.broker = broker
        self.strategy = strategy
        self.paper = paper
        self.risk = risk
        self.cache = cache
        self.candle_builder = candle_builder

        logger.success("Trading Engine Initialized")