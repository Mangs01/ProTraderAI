from loguru import logger


class LiveCache:

    def __init__(self):

        self.data = {}

        logger.info("Live Cache Initialized")

    def update(self, token, tick):

        self.data[token] = tick

    def get(self, token):

        return self.data.get(token)

    def all(self):

        return self.data