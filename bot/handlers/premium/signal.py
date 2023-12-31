import logging
import requests
import os
from telegram import Update
from telegram.ext import CallbackContext, CommandHandler
from bot.utils import log_command_usage, restricted, command_usage_example
from config.settings import X_RAPIDAPI_KEY
from bot.utils import PlotChart
from bot.handlers.premium.stats import StatsHandler

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SignalHandler:
    @staticmethod
    @restricted
    @log_command_usage("general_signal")
    @command_usage_example("/signal BTCUSDT")
    def signal_handler(update: Update, context: CallbackContext):
        logger.info("General Signal command received")
        if len(context.args) < 2:
            update.message.reply_text("Please provide both symbol and timeframe.")
            return

        symbol = context.args[0]
        timeframe = context.args[1]

        # Send a Loading message and tag it so we can delete it later
        loading_message = update.message.reply_text(
            "Loading Data... Please wait.", quote=True
        )

        # Fetch indicator data
        rsi_data = StatsHandler.fetch_rsi_data(symbol, "rsi", timeframe)
        obv_data = StatsHandler.fetch_obv_data(symbol, "obv", timeframe)
        mfi_data = StatsHandler.fetch_mfi_data(symbol, "mfi", timeframe)
        macd_data = StatsHandler.fetch_macd_data(symbol, "macd", timeframe)

        # Calculate composite score
        composite_score = 0

        # RSI overbought/oversold
        rsi_status = ""
        if "rsi" in rsi_data and rsi_data["rsi"]:
            latest_rsi = rsi_data["rsi"][-1]
            if latest_rsi > 70:
                rsi_status = "overbought"
                composite_score -= 1.5  # Increased weight for RSI
            elif latest_rsi < 30:
                rsi_status = "oversold"
                composite_score += 1.5  # Increased weight for RSI

        # OBV rising/falling
        obv_status = ""
        if "obv" in obv_data and obv_data["obv"]:
            latest_obv = obv_data["obv"][-1]
            previous_obv = obv_data["obv"][-2]
            if latest_obv > previous_obv:
                obv_status = "rising"
                composite_score += 1
            elif latest_obv < previous_obv:
                obv_status = "falling"
                composite_score -= 1

        # MFI overbought/oversold
        mfi_status = ""
        if "mfi" in mfi_data and mfi_data["mfi"]:
            latest_mfi = mfi_data["mfi"][-1]
            if latest_mfi > 80:
                mfi_status = "overbought"
                composite_score -= 1
            elif latest_mfi < 20:
                mfi_status = "oversold"
                composite_score += 1

        # define 2 dictionaries to store the last 2 periods of MACD data
        latest_macd = {}
        previous_macd = {}

        # filter and store the last 2 periods of MACD data
        if "macd" in macd_data and macd_data["macd"]:
            latest_macd = macd_data["macd"][-1]
            previous_macd = macd_data["macd"][-2]

        # check if the histogram is rising or falling
        if (
            "histogram" in latest_macd
            and "histogram" in previous_macd
            and latest_macd["histogram"] > previous_macd["histogram"]
        ):
            macd_status = "MACD histogram is rising"
        elif (
            "histogram" in latest_macd
            and "histogram" in previous_macd
            and latest_macd["histogram"] < previous_macd["histogram"]
        ):
            macd_status = "MACD histogram is falling"
        else:
            macd_status = "MACD histogram is flat"

        # if the macd_stats is rising, add 1 to the composite score
        if macd_status == "MACD histogram is rising":
            composite_score += 1
        # if the macd_stats is falling, subtract 1 from the composite score
        elif macd_status == "MACD histogram is falling":
            composite_score -= 1

        # Generate general signal based on composite score
        if composite_score > 0:
            general_signal = "Bullish"
        elif composite_score < 0:
            general_signal = "Bearish"
        else:
            general_signal = "Neutral"

        # Send general signal message
        update.message.reply_text(f"General Signal for {symbol}: {general_signal}")
        # add reasoning for the signal here (explain the composite score and why it is bullish/bearish/neutral)
        update.message.reply_text(
            "The general signal is based on the following indicators:"
        )
        # add the individual signals here and include the status of each indicator
        update.message.reply_text(
            f"RSI: {rsi_status} (Current RSI: {latest_rsi})\n"
            f"OBV: {obv_status} (Current OBV: {latest_obv})\n"
            f"MFI: {mfi_status} (Current MFI: {latest_mfi})\n"
            f"{macd_status} (Current MACD hist: {latest_macd['histogram']})"
        )
        # Explain the composite score
        update.message.reply_text(
            f"The composite score is {composite_score}.\n"
            "A positive composite score indicates a bullish signal.\n"
            "A negative composite score indicates a bearish signal.\n"
            "A composite score of 0 indicates a neutral signal."
        )

        # If the composite score is positive but OBV is falling, or if the composite score is negative but OBV is rising, send a warning message
        if (composite_score > 0 and obv_status == "falling") or (
            composite_score < 0 and obv_status == "rising"
        ):
            update.message.reply_text(
                "Warning: The OBV indicator does not confirm the general signal. This could indicate a less reliable signal."
            )
        # If there's a divergence between price and RSI, send a warning message

        # Update the loading message
        loading_message.edit_text("Generating The Chart...")

        # Plot chart
        chart_file = PlotChart.plot_ohlcv_chart(symbol, timeframe)

        # Update the loading message to indicate that the chart has been generated
        loading_message.edit_text("Chart generated. Sending chart...")

        # Send chart to user and then delete it
        if chart_file:
            with open(chart_file, "rb") as f:
                context.bot.send_photo(chat_id=update.effective_chat.id, photo=f)
            os.remove(chart_file)

        # Delete the loading message
        loading_message.delete()
        logger.info("Stats command completed")

    @staticmethod
    def command_handler() -> CommandHandler:
        return CommandHandler("signal", SignalHandler.signal_handler, pass_args=True)
