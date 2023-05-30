import logging
import requests
import os
from telegram import Update
from telegram.ext import CallbackContext, CommandHandler
from bot.utils import restricted, log_command_usage, PlotChart, command_usage_example
from config.settings import X_RAPIDAPI_KEY
from cachetools import cached, TTLCache

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize cache with a TTL of 4 hours
cache = TTLCache(maxsize=100, ttl=14400)


class StatsHandler:
    @staticmethod
    @cached(cache)
    def fetch_data(symbol: str, endpoint: str):
        url = f"https://cryptocurrencies-technical-study.p.rapidapi.com/crypto/{endpoint}/{symbol}/4h"
        headers = {
            "X-RapidAPI-Key": X_RAPIDAPI_KEY,
            "X-RapidAPI-Host": "cryptocurrencies-technical-study.p.rapidapi.com",
        }
        response = requests.get(url, headers=headers)
        return response.json()

    @staticmethod
    def filter_patterns(data: dict):
        return {
            k: v
            for k, v in data.items()
            if v is True and k not in ["timestamp", "symbol", "timeframe", "prices"]
        }

    @staticmethod
    def generate_patterns_message(symbol: str, patterns: dict):
        return f"Patterns for {symbol}:\n\n" + "\n".join(patterns.keys())

    @staticmethod
    def send_patterns_message(update: Update, patterns_message: str):
        update.message.reply_text(patterns_message)
        logger.info("Patterns message sent")

    @staticmethod
    def fetch_indicator_data(symbol: str, indicator: str):
        url = f"https://cryptocurrencies-technical-study.p.rapidapi.com/crypto/{indicator}/{symbol}/4h/14"
        headers = {
            "X-RapidAPI-Key": X_RAPIDAPI_KEY,
            "X-RapidAPI-Host": "cryptocurrencies-technical-study.p.rapidapi.com",
        }
        response = requests.get(url, headers=headers)
        data = response.json()
        return data

    @staticmethod
    @restricted
    @log_command_usage("stats")
    @command_usage_example("/stats BTCUSDT")
    def stats(update: Update, context: CallbackContext):
        logger.info("Stats command received")
        symbol = context.args[0] if context.args else "BTCUSDT"

        # Send a loading message
        message = update.message.reply_text("Fetching data...")

        # Fetch pattern data
        pattern_data = StatsHandler.fetch_data(symbol, "patterns")
        patterns = StatsHandler.filter_patterns(pattern_data)
        patterns_message = StatsHandler.generate_patterns_message(symbol, patterns)

        # Send patterns message
        StatsHandler.send_patterns_message(update, patterns_message)

        # Fetch RSI data
        rsi_data = StatsHandler.fetch_indicator_data(symbol, "rsi")

        # TODO: Check for MACD crossover, RSI overbought/oversold, RSI divergence, and OBV divergence
        # RSI overbought/oversold
        if "rsi" in rsi_data and rsi_data["rsi"]:
            latest_rsi = rsi_data["rsi"][-1]
            if latest_rsi > 70:
                rsi_status = "RSI overbought"
            elif latest_rsi < 30:
                rsi_status = "RSI oversold"
            else:
                rsi_status = "RSI is in normal range"
            update.message.reply_text(f"Latest RSI: {latest_rsi}. {rsi_status}")
        else:
            logger.error("RSI data not found in API response")
            update.message.reply_text(
                "Unable to check RSI overbought/oversold status due to missing data"
            )

        logger.info("RSI overbought/oversold checked")

        # Plot chart
        chart_file = PlotChart.plot_ohlcv_chart(symbol, "4h")

        # Update the loading message to indicate that the chart has been generated
        message.edit_text("Chart generated. Sending chart...")

        # Send chart to user and then delete it
        if chart_file:
            with open(chart_file, "rb") as f:
                context.bot.send_photo(chat_id=update.effective_chat.id, photo=f)
            os.remove(chart_file)

        # Update the loading message to indicate that the chart has been sent and the command has completed
        message.edit_text("Chart sent. Command completed.")
        logger.info("Stats command completed")

    @staticmethod
    def command_handler() -> CommandHandler:
        return CommandHandler("stats", StatsHandler.stats, pass_args=True)