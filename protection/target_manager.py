from loguru import logger


class TargetManager:

    def __init__(self):

        self.target = None
        self.side = None

        logger.info("Target Manager Initialized")

    def set(self, target, side):

        self.target = target
        self.side = side

        logger.info(
            f"Target Set : {target:.2f} | Side : {side}"
        )

    def hit(self, price):

        if self.target is None:
            return False

        if self.side == "BUY":
            return price >= self.target

        if self.side == "SELL":
            return price <= self.target

        return False

    def reset(self):

        self.target = None
        self.side = None

        logger.info("Target Reset")