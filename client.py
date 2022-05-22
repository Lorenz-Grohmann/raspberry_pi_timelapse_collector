import io
import socket
import struct
import time
import logging
import os
import picamera
from datetime import date
from PIL import Image

from conf_client import *

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)



failed_upload = 2147483647


def send_image(data, size, date):
    result = False
    try:
        client_socket = socket.socket()
        client_socket.connect((SERVER_ADDR, SERVER_PORT))
        connection = client_socket.makefile("wb")

        collection_data = TIMELAPS_NAME.encode()
        connection.write(struct.pack('<L', len(collection_data)))
        connection.flush()
        connection.write(collection_data)

        connection.write(struct.pack('<L', size))
        connection.write(struct.pack('<L', date))
        connection.flush()

        connection.write(data)
        connection.write(struct.pack('<L', 0))
        client_socket.close()
        result =  True
    finally:
        client_socket.close()
        return result

def safe_image(data, date):
    img = Image.open(io.BytesIO(data))
    path = LOCAL_STORAGE_PATH + "/%s_%s.jpeg" % (TIMELAPS_NAME,date)
    img.save(path, "JPEG")
    logger.info("Photo Saved to %s" % path)


def uplaod_local_pictures():
    result = False
    try:
        client_socket = socket.socket()
        client_socket.connect((SERVER_ADDR, SERVER_PORT))
        connection = client_socket.makefile("wb")
        collection_data = TIMELAPS_NAME.encode()
        connection.write(struct.pack('<L', len(collection_data)))
        connection.flush()
        connection.write(collection_data)

        for file in os.listdir(LOCAL_STORAGE_PATH):
            path = LOCAL_STORAGE_PATH + "/" + file
            date = int(file.replace(".jpeg","").split("_")[1])
            image = Image.open(path)
            image.verify()
            image = Image.open(path)
            data = io.BytesIO()
            image.save(data, format="JPEG")
            size = data.getbuffer().nbytes

            connection.write(struct.pack('<L', size))
            connection.flush()
            connection.write(struct.pack('<L', date))
            connection.flush()
            data.seek(0)
            connection.write(data.read())
            os.remove(path) 
            logger.info("Uploaded %s" % file)
        
        connection.write(struct.pack('<L', 0))
        client_socket.close()
        result = True
        time.sleep(0.2)
    finally:
        client_socket.close()
        return result



def main():
    global failed_upload
    camera = picamera.PiCamera()
    camera.resolution = (1280, 720)
    # Start a preview and let the camera warm up for 2 seconds
    camera.start_preview()
    time.sleep(2)
    stream = io.BytesIO()
    if len(os.listdir(LOCAL_STORAGE_PATH)) !=0:
        logger.info("%s Local Pictures Present.. Attempting Upload!" % len(os.listdir(LOCAL_STORAGE_PATH)))
        if uplaod_local_pictures():
            logger.info("Upload Succesfull!")
        else:
            logger.info("Upload of Local Pictures Failed! Attempting again in 10 minutes")
            failed_upload = int(time.time()) + 600


    for foo in camera.capture_continuous(stream, 'jpeg'):
        image_date = int(time.time())
        image_size = stream.tell()
        stream.seek(0)
        image_data = stream.read()

        stream.seek(0)
        stream.truncate()

        if failed_upload < int(time.time()):
            logger.info("Attempting Uplaod of Local Pictures")
            if uplaod_local_pictures():
                failed_upload = 2147483647
                logger.info("Upload Succesfull!")
            else:
                logger.info("Upload of local pictures Failed! Attempting again in 10 minutes")
                failed_upload = int(time.time()) + 600


        if failed_upload == 2147483647:
            if not send_image(image_data, image_size, image_date):
                logger.info("Upload of Picture Failed! Pictures will be stored locally and a collective upload will be attempted in 10 Minutes")
                safe_image(image_data, image_date)
                failed_upload = int(time.time()) + 600
            else:
                logger.info("Picture Uploaded")
        else:
            safe_image(image_data, image_date)

        stream.seek(0)
        stream.truncate()
        time.sleep(TIMELAPSE_INTERVAL)

main()