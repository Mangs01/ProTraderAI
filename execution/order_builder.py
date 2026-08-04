from loguru import logger


class OrderBuilder:

    @staticmethod
    def market_order(
        transaction_type,
        tradingsymbol,
        symboltoken,
        quantity=1,
        exchange="NSE"
    ):

        order = {

            "variety": "NORMAL",

            "tradingsymbol": tradingsymbol,

            "symboltoken": symboltoken,

            "transactiontype": transaction_type,

            "exchange": exchange,

            "ordertype": "MARKET",

            "producttype": "INTRADAY",

            "duration": "DAY",

            "quantity": str(quantity)

        }

        logger.success("Order Payload Created")

        return order