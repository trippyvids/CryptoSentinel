import requests
from decimal import Decimal
from telegram import Update, ParseMode
from telegram.ext import CallbackContext
from config.settings import X_RAPIDAPI_KEY, MY_POSTGRESQL_URL
from bot.utils import log_command_usage
import logging

logger = logging.getLogger(__name__)

# setup database
from bot.database import PriceAlertRequest, Session

class PriceAlertHandler:
    @staticmethod
    def request_price_alert(update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        symbol, price_level = context.args
        price_level = Decimal(price_level)

        session = Session()
        price_alert_requests = PriceAlertRequest(user_id=user_id, symbol=symbol, price_level=price_level)
        session.add(price_alert_requests)
        session.commit()

        update.message.reply_text(f"Your request for a price alert has been successfully set up! You will receive a notification when the price of {symbol} reaches {price_level}.")