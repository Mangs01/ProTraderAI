from loguru import logger


class PaperEngine:

    def __init__(self):

        self.position = None

    def buy(self, price):

        if self.position is not None:

            logger.warning("Already in Position")
            return

        self.position = {
            "side": "BUY",
            "entry": price
        }

        logger.success(f"PAPER BUY @ {price}")

    def sell(self, price):

        if self.position is not None:

            logger.warning("Already in Position")
            return

        self.position = {
            "side": "SELL",
            "entry": price
        }

        logger.warning(f"PAPER SELL @ {price}")

    def exit(self, price):

        if self.position is None:

            logger.info("No Position")
            return

        if self.position["side"] == "BUY":

            pnl = price - self.position["entry"]

        else:

            pnl = self.position["entry"] - price

        logger.success(f"P&L : {round(pnl,2)}")

        self.position = None