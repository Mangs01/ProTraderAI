from loguru import logger

from execution.order_builder import OrderBuilder
from config.settings import SYMBOL, SYMBOL_TOKEN
from risk.risk_manager import RiskManager
from position.position_manager import PositionManager

class OrderManager:

    def __init__(self, broker):

        self.broker = broker

        # Risk Manager
        self.risk = RiskManager(
            capital=100000,
            risk_percent=1,
            max_daily_loss=2000,
            max_trade_per_day=5
        )

        self.position = PositionManager()

    # ----------------------------------------

    def buy(self, entry_price, stop_loss):

        if self.position.has_position():

            logger.warning("Position Already Open")

            return

        self.position.open_position(
            side="BUY",
            entry_price=entry_price,
            quantity=quantity
        )

        if not self.risk.can_trade():
            return

        if self.position.has_position():

            logger.warning("Position Already Open")

            return

        self.position.open_position(
            side="SELL",
            entry_price=entry_price,
            quantity=quantity
        )

        quantity = self.risk.position_size(
            entry_price,
            stop_loss
        )

        logger.success(
            f"BUY ORDER | Qty={quantity}"
        )

        order = OrderBuilder.market_order(

            tradingsymbol=SYMBOL,

            symboltoken=SYMBOL_TOKEN,

            transaction_type="BUY",

            quantity=quantity

        )

        logger.info(order)

        # Live Trading (Future)
        # order_id = self.broker.place_order(order)

    # ----------------------------------------

    def sell(self, entry_price, stop_loss):

        if not self.risk.can_trade():
            return

        quantity = self.risk.position_size(
            entry_price,
            stop_loss
        )

        logger.warning(
            f"SELL ORDER | Qty={quantity}"
        )

        order = OrderBuilder.market_order(

            tradingsymbol=SYMBOL,

            symboltoken=SYMBOL_TOKEN,

            transaction_type="SELL",

            quantity=quantity

        )

        logger.info(order)

        # Live Trading (Future)
        # order_id = self.broker.place_order(order)

    # ----------------------------------------

    def exit(self):

        if self.position.has_position():

            self.position.close_position()

        logger.info("EXIT ORDER")