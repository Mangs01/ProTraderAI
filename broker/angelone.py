from SmartApi import SmartConnect
import pyotp
from loguru import logger

from config.settings import API_KEY, CLIENT_CODE, MPIN, TOTP_SECRET


class AngelOneBroker:

    def __init__(self):

        logger.info("Angel One Broker Module Loaded")

        self.api = SmartConnect(api_key=API_KEY)

        self.API_KEY = API_KEY
        self.CLIENT_CODE = CLIENT_CODE

        self.jwt_token = None
        self.refresh_token = None
        self.feed_token = None

    def login(self):

        totp = pyotp.TOTP(TOTP_SECRET).now()

        data = self.api.generateSession(
            CLIENT_CODE,
            MPIN,
            totp
        )

        self.jwt_token = data["data"]["jwtToken"]

        self.refresh_token = data["data"]["refreshToken"]

        self.feed_token = self.api.getfeedToken()

        logger.success("Login Successful")

        return data

    def get_profile(self):
        profile = self.api.getProfile(self.refresh_token)
        logger.success("Profile Loaded")
        return profile


    def get_funds(self):
        funds = self.api.rmsLimit()
        logger.success("Funds Loaded")
        return funds


    def get_holdings(self):
        holdings = self.api.holding()
        logger.success("Holdings Loaded")
        return holdings


    def get_positions(self):
        positions = self.api.position()
        logger.success("Positions Loaded")
        return positions
    
    def get_ltp(self, exchange, tradingsymbol, symboltoken):

        try:

            data = self.api.ltpData(
                exchange,
                tradingsymbol,
                symboltoken
            )

            logger.success("LTP Loaded")

            return data

        except Exception as e:

            logger.error(e)

            return None
    
    def order_book(self):

        try:

            orders = self.api.orderBook()

            logger.success("Order Book Loaded")

            return orders

        except Exception as e:

            logger.error(e)

            return None
    
    def trade_book(self):

        try:

            trades = self.api.tradeBook()

            logger.success("Trade Book Loaded")

            return trades

        except Exception as e:

            logger.exception(e)

            return None

    def get_historical_data(
        self,
        exchange,
        symboltoken,
        interval,
        fromdate,
        todate
   ):

        params = {

            "exchange": exchange,
            "symboltoken": symboltoken,
            "interval": interval,
            "fromdate": fromdate,
            "todate": todate

        }

        try:

            logger.info(f"Downloading Candle Data : {params}")

            data = self.api.getCandleData(params)

            logger.success("Historical Data Loaded")

            return data

        except Exception as e:

            logger.exception(e)

            return None
        
    def place_order(self, order):

    
        try:

            order_id = self.api.placeOrder(order)

            logger.success(f"Order Placed : {order_id}")

            return order_id

        except Exception as e:

            logger.exception(e)

            return None
    
    def modify_order(self, order):

        try:

            response = self.api.modifyOrder(order)

            logger.success("Order Modified")

            return response

        except Exception as e:

            logger.exception(e)

            return None
    
    def cancel_order(self, order_id):

        try:

            response = self.api.cancelOrder(order_id)

            logger.success("Order Cancelled")

            return response

        except Exception as e:

            logger.exception(e)

            return None
    
    def get_jwt_token(self):
        return self.jwt_token


    def get_refresh_token(self):
        return self.refresh_token


    def get_feed_token(self):
        return self.feed_token