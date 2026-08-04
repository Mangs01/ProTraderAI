from loguru import logger


class PositionManager:

    def __init__(self):

        self.position = None
        self.entry_price = None
        self.quantity = 0

        logger.info("Position Manager Initialized")

    # ------------------------------------

    def has_position(self):

        return self.position is not None

    # ------------------------------------

    def open_position(
        self,
        side,
        entry_price,
        quantity
    ):

        self.position = side
        self.entry_price = entry_price
        self.quantity = quantity

        logger.success(
            f"Position Opened : {side} @ {entry_price}"
        )

    # ------------------------------------

    def close_position(self):

        logger.warning("Position Closed")

        self.position = None
        self.entry_price = None
        self.quantity = 0

    # ------------------------------------

    def current_position(self):

        return self.position