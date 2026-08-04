from loguru import logger


class StopLossManager:

    def __init__(self):

        self.stop_loss = None

        logger.info("Stop Loss Manager Initialized")

    # ----------------------------------------

    def set(self, stop_loss):

        self.stop_loss = stop_loss

        logger.success(f"Stop Loss Set : {stop_loss}")

    # ----------------------------------------

    def get(self):

        return self.stop_loss

    # ----------------------------------------

    def hit(self, price):

        if self.stop_loss is None:
            return False

        return price <= self.stop_loss

    # ----------------------------------------

    def clear(self):

        self.stop_loss = None

        logger.info("Stop Loss Cleared")