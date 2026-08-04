from loguru import logger


class RiskManager:

    def __init__(
        self,
        capital,
        risk_percent=1,
        max_daily_loss=2000,
        max_trade_per_day=5
    ):

        self.capital = capital
        self.risk_percent = risk_percent
        self.max_daily_loss = max_daily_loss
        self.max_trade_per_day = max_trade_per_day

        self.daily_loss = 0
        self.trade_count = 0

    # ------------------------------------

    def risk_amount(self):

        return self.capital * self.risk_percent / 100

    # ------------------------------------

    def position_size(
        self,
        entry_price,
        stop_loss
    ):

        risk = self.risk_amount()

        per_share_risk = abs(entry_price - stop_loss)

        if per_share_risk == 0:
            return 0

        qty = int(risk / per_share_risk)

        logger.info(f"Position Size : {qty}")

        return max(qty, 1)

    # ------------------------------------

    def can_trade(self):

        if self.daily_loss >= self.max_daily_loss:

            logger.error("Daily Loss Limit Reached")

            return False

        if self.trade_count >= self.max_trade_per_day:

            logger.error("Maximum Trades Reached")

            return False

        return True

    # ------------------------------------

    def update_trade(self, pnl):

        self.trade_count += 1

        if pnl < 0:

            self.daily_loss += abs(pnl)

        logger.info(
            f"Trades : {self.trade_count} | Daily Loss : {self.daily_loss}"
        )

    # ------------------------------------

    def reset(self):

        self.daily_loss = 0
        self.trade_count = 0

        logger.info("Risk Manager Reset")