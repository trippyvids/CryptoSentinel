import requests
import logging
import ccxt
import datetime
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import ta
import os
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import CallbackContext
from bot.utils import restricted
from config.settings import LUNARCRUSH_API_KEY
from bot.utils import log_command_usage

from cachetools import TTLCache

cotd_cache = TTLCache(maxsize=1, ttl=3600)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CotdHandler:
    @staticmethod
    def fetch_ohlcv_data(symbol):
        """Fetch OHLCV data from Binance and return as a DataFrame"""
        try:
            exchange = ccxt.bybit()
            ohlcv = exchange.fetch_ohlcv(symbol.upper() + "/USDT", "4h")
        except Exception as e:
            logger.exception("Error fetching OHLCV data")
            raise e

        # Filter data to display only the last 4 weeks
        two_weeks_ago = datetime.now() - timedelta(weeks=4)
        ohlcv = [
            entry
            for entry in ohlcv
            if datetime.fromtimestamp(entry[0] // 1000) >= two_weeks_ago
        ]

        # Convert timestamp to datetime objects
        for entry in ohlcv:
            entry[0] = datetime.fromtimestamp(entry[0] // 1000)

        # Create a DataFrame and set 'Date' as the index
        df = pd.DataFrame(
            ohlcv, columns=["Date", "Open", "High", "Low", "Close", "Volume"]
        )
        df.set_index("Date", inplace=True)

        return df

    @staticmethod
    def add_indicators(df):
        """Add RSI and moving averages to the DataFrame"""
        # Add RSI
        delta = df["Close"].diff()
        gain, loss = delta.where(delta > 0, 0), delta.where(delta < 0, 0).abs()
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        df["RSI"] = rsi

        # Add moving averages
        df["SMA21"] = ta.trend.sma_indicator(df["Close"], window=21)
        df["SMA50"] = ta.trend.sma_indicator(df["Close"], window=50)

        return df

    @staticmethod
    def plot_ohlcv_chart(df, symbol):
        """Plot OHLCV chart and save as PNG image"""
        # Create a Plotly figure
        fig = go.Figure()

        # Add OHLCV data
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df["Open"],
                high=df["High"],
                low=df["Low"],
                close=df["Close"],
                name="Price",
            )
        )

        # Add moving averages
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["SMA21"],
                mode="lines",
                name="SMA21",
                line=dict(color="orange", width=1),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["SMA50"],
                mode="lines",
                name="SMA50",
                line=dict(color="blue", width=1),
            )
        )

        # Customize the layout
        fig.update_layout(
            title=f"{symbol} OHLCV Chart",
            xaxis=dict(
                type="date",
                tickformat="%H:%M %b-%d",
                tickmode="auto",
                nticks=10,
                rangeslider=dict(visible=False),
            ),
            yaxis=dict(title="Price (USDT)"),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
            template="plotly_dark",
            margin=dict(b=40, t=40, r=40, l=40),
        )

        # Save the chart as a PNG image
        fig.write_image(f"charts/{symbol}_chart.png", scale=1.5, width=1000, height=600)

    @staticmethod
    @log_command_usage("cotd")
    def coin_of_the_day(update: Update, context: CallbackContext):
        # Fetch Coin of the Day data from LunarCrush API
        url = "https://lunarcrush.com/api3/coinoftheday"
        headers = {"Authorization": f"Bearer {LUNARCRUSH_API_KEY}"}

        loading_message = update.message.reply_text("Fetching Coin of the Day...", quote=True)

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            logger.exception(
                "Connection error while fetching Coin of the Day from LunarCrush API"
            )
            update.message.reply_text(
                "Error connecting to LunarCrush API. Please try again later."
            )
            return
        
        # Update the loading message with the Coin of the Day data
        loading_message.edit_text(
            f"Coin of the Day: {data['name']} ({data['symbol']}).\n\n"
            f"Loading OHLCV chart...\n"
        )


        if "name" in data and "symbol" in data:
            coin_name = data["name"]
            coin_symbol = data["symbol"]

            # Fetch and plot the OHLCV chart
            try:
                df = CotdHandler.fetch_ohlcv_data(coin_symbol)
                df = CotdHandler.add_indicators(df)
                CotdHandler.plot_ohlcv_chart(df, coin_symbol)
            except Exception as e:
                logger.exception("Error while plotting the OHLCV chart")
                update.message.reply_text(
                    f"Coin of the Day: {coin_name} ({coin_symbol}).\n\n"
                    "Can't generate the chart. Symbol not listed on available exchanges."
                )
                return

            # Send the chart and the Coin of the Day message
            image_path = f"charts/{coin_symbol}_chart.png"
            try:
                with open(image_path, "rb") as f:
                    context.bot.send_photo(chat_id=update.effective_chat.id, photo=f)
                update.message.reply_text(
                    f"Coin of the Day: {coin_name} ({coin_symbol})"
                )

                # Delete the image file after sending it
                os.remove(image_path)
            except Exception as e:
                logger.exception(
                    "Error while sending the chart and the Coin of the Day message"
                )
                update.message.reply_text(
                    "Error while sending the chart and the Coin of the Day message. Please try again later."
                )
                return

            # Delete the loading message
            context.bot.delete_message(
                chat_id=update.effective_chat.id, message_id=loading_message.message_id
            )


        else:
            logger.error("Error in LunarCrush API response: Required data not found")
            update.message.reply_text(
                "Error fetching Coin of the Day data. Please try again later."
            )
