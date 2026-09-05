from loguru import logger


class StopLossManager:

    def __init__(self):

        self.stop_loss = None
        self.side = None

        logger.info("Stop Loss Manager Initialized")

    def set(self, stop_loss, side):

        self.stop_loss = stop_loss
        self.side = side

        logger.info(
            f"Stop Loss Set : {stop_loss:.2f} | Side : {side}"
        )

    def hit(self, price):

        if self.stop_loss is None:
            return False

        if self.side == "BUY":
            return price <= self.stop_loss

        if self.side == "SELL":
            return price >= self.stop_loss

        return False

    def reset(self):

        self.stop_loss = None
        self.side = None

        logger.info("Stop Loss Reset")