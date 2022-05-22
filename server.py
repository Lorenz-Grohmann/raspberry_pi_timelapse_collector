import logging
import io
import socket
import struct
import _thread
from PIL import Image
from telegram.ext import Updater, CommandHandler
from pathlib import Path
from datetime import datetime

from conf_server import *


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)


telegram_count = {}

def get_id(update, context):
    user = update["_effective_user"]["id"]
    context.bot.send_message(update["message"]["chat"]["id"], str(user))


def on_new_client(clientsocket, addr):
    file = clientsocket.makefile()
    logger.info("New Connection form " + str(addr[0]))
    connection = clientsocket.makefile("rwb")
    try:
        collection_len = struct.unpack('<L', connection.read(struct.calcsize('<L')))[0]
        collection = connection.read(collection_len).decode()
        if not collection in telegram_count:
            telegram_count[collection] = TELEGRAM_SEND_INTERVAL

        while True:
            image_len = struct.unpack('<L', connection.read(struct.calcsize('<L')))[0]
            if not image_len:
                break
            image_date = struct.unpack('<L', connection.read(struct.calcsize('<L')))[0]
            image_stream = io.BytesIO()
            image_stream.write(connection.read(image_len))
            image_stream.seek(0)
            image = Image.open(image_stream)
            try:
                image.verify()
            except:
                logger.info("Image verification failed.. Skipping")
                continue
            #image = Image.open(image_stream) #Reopen is neccesary after verify...
            save_image(image_stream, collection, image_date)
            if(telegram_count[collection] == TELEGRAM_SEND_INTERVAL):
                telegram_count[collection] = 0
                send_image(image_stream)
            else:
                telegram_count[collection] = telegram_count[collection]+1
    finally:
        file.close()
        clientsocket.close()
        logger.info("Connection from " + str(addr[0]) + " has ended.")


def save_image(image_stream, collection, date):
    dir = COLLECTION_PATH+"/"+collection
    Path(dir).mkdir(parents=True, exist_ok=True)
    date_str = datetime.utcfromtimestamp(date).strftime('%Y-%m-%d_%H:%M:%S')
    path = dir+"/%s.jpeg" % date_str
    image = Image.open(image_stream)
    image.save(path)
    logger.info("New image saved to %s" % path)


def send_image(image_stream):

    image = Image.open(image_stream)
    imgByteArr = io.BytesIO()
    image.save(imgByteArr, format=image.format)
    imgByteArr = imgByteArr.getvalue()
    bot.send_photo(CHAT_ID, imgByteArr)


def main():
    global bot
    updater = Updater(TELEGRAM_BOT_API_KEY, use_context=True)
    dp = updater.dispatcher
    bot = updater.bot
    job_queue = updater.job_queue
    dp.add_handler(CommandHandler("getID", get_id))
    updater.start_polling()
    server_socket = socket.socket()
    server_socket.bind(('0.0.0.0', SERVER_PORT))
    server_socket.listen(0)
    while True:
        logger.info("Starting to listen for Connections")
        c, addr = server_socket.accept()
        _thread.start_new_thread(on_new_client, (c, addr))


main()