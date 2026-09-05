from loguru import logger


class TradeMonitor:

    def __init__(
        self,
        trade_manager,
        position_manager,
        stop_loss_manager,
        target_manager
    ):

        self.trade = trade_manager
        self.position = position_manager
        self.stop_loss = stop_loss_manager
        self.target = target_manager

        logger.info("Trade Monitor Loaded")

    # ----------------------------------------

    def check(self, current_price):

        if not self.trade.is_active():
            return "NO_TRADE"

        # Stop Loss
        if self.stop_loss.hit(current_price):

            logger.warning(
                f"STOP LOSS HIT : {current_price}"
            )

            return "STOP_LOSS"

        # Target
        if self.target.hit(current_price):

            logger.success(
                f"TARGET HIT : {current_price}"
            )

            return "TARGET"

        return "HOLD"