#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# require: python >= 3.8

import argparse
import os
import json
import time
import threading
import multiprocessing as mp
from venv import logger

import tornado.ioloop
import tornado.web
from tornado.log import enable_pretty_logging
from tornado.websocket import WebSocketHandler
from core.device import HmDevice
from core.hmdriver2 import InjectGestureError


class CorsMixin:
    def initialize(self):
        self.set_header('Connection', 'close')
        self.request.connection.no_keep_alive = True

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')

    def options(self):
        # no body
        self.set_status(204)
        self.finish()

class MainHandler(CorsMixin, tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")

class MJPEGHandler(CorsMixin, tornado.web.RequestHandler):
    CAP_READER = None
    LAST_FRAME = None
    
    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)
        self.stop_event = threading.Event()
        self.read_frame_th = threading.Thread(target=self._read_frame)
        self.read_frame_th.daemon = True
        self.read_frame_th.start()
    
    def prepare(self):
        client_ip = self.request.remote_ip
        logger.info(f"Request from {client_ip}")
    
    @tornado.gen.coroutine
    def get(self):
        self.set_header("Content-type", "multipart/x-mixed-replace;boundary=--frame")
        while True:
            try:                    
                if self.LAST_FRAME is not None:
                    self.write(b'--frame\r\n')
                    self.write(b'Content-Type: image/jpeg\r\n\r\n' + bytearray(self.LAST_FRAME) + b'\r\n')
                    logger.debug("flush frame")
                    yield self.flush()
                else:
                    logger.debug("no frame")
            except Exception as e:
                pass
            yield tornado.gen.sleep(0.05)    
            
    def _read_frame(self):
        while True:
            try:
                frame = self.CAP_READER.get_content()
                if frame is not None:
                    self.LAST_FRAME = frame
            except Exception as e:
                pass
            time.sleep(0.05)


class MiniTouchWSHandler(CorsMixin, WebSocketHandler):
    
    DEVICE: HmDevice = None
    EVETS_QUEUE: mp.Queue = mp.Queue()
    LAST_GESTURE = None
    
    def initialize(self):
        self.last_event_time = 0
        self.stop_event = threading.Event()
        self.mouse_events_th = threading.Thread(target=self.on_mouse_event)
        self.mouse_events_th.daemon = True
        self.mouse_events_th.start()
    
    def check_origin(self, origin):
        return True
    
    def open(self):
        logger.info("connection created")
    
    def on_message(self, message):
        logger.info(f"Received message: {message}")
        msg = json.loads(message)
        action = msg.get('action')
        client_time = msg.get('ct')
        data = msg.get('data')
        if action == 'ping':
            self.send_pong(client_time)
        elif action == 'back':
            self.DEVICE.go_back()
        elif action == 'key':
            key = data.get('key')
            logger.info("press key: " + key)
            self.DEVICE.press_key_ex(key)
        else:
            self.add_mouse_event(action, client_time, data)
        
    def on_close(self):
        logger.info("connection closed")
        
    def send_pong(self, client_time):
        server_time = int(time.time() * 1000)
        self.write_message(json.dumps({
            'a': 'pong',
            'ct': client_time,
            'st': server_time
        }))
        
    def on_mouse_event(self):
        screen_width, screen_height = self.DEVICE.display_size
        screen_size = {
            'w': screen_width,
            'h': screen_height
        }
        last_event_time = 0
        self.LAST_GESTURE = None
        while not self.stop_event.is_set():
            if self.EVETS_QUEUE.empty():
                time.sleep(0.01)
                continue
            
            event = self.EVETS_QUEUE.get(timeout=0.01)
            if event is not None:
                action = event.get('action')
                timestamp = event.get('timestamp')
                data = event.get('data')
                try:
                    if action == 'submit':
                        logger.info(f"get mouse event {action} {timestamp} {data}")
                        last_event_time = 0
                        if self.LAST_GESTURE is not None:
                            self.LAST_GESTURE.action()
                            self.LAST_GESTURE = None
                        else:
                            logger.info(f"no gesture")
                    else:
                        x, y = self.coords(screen_size, data.get('s'), data.get('x'), data.get('y'))
                        if last_event_time == 0 or action != 'move':
                            timediff = 0.1
                        else:
                            timediff = (timestamp - last_event_time) / 1000
                        last_event_time = timestamp
                        if action == 'down' or self.LAST_GESTURE is None: 
                            try:
                                self.LAST_GESTURE = self.DEVICE.gesture.start(x, y, 0.1)
                            except InjectGestureError as e:
                                self.LAST_GESTURE = self.DEVICE.gesture
                        elif action == 'move':
                            self.LAST_GESTURE.move(x, y, timediff)
                        elif action == 'hover':
                            logger.info(f"hover {x} {y} {timediff}")
                            self.LAST_GESTURE.pause(x, y, timediff)
                except Exception as e:
                    logger.exception(e)
        
    def add_mouse_event(self, action, timestamp, data = None):
        self.EVETS_QUEUE.put_nowait({
            'action': action,
            'timestamp': timestamp,
            'data': data
        })

    def coords(self, screen_size, container_size, x, y):
        screen_width = screen_size.get('w')
        screen_height = screen_size.get('h')
        container_width = container_size.get('w')
        container_height = container_size.get('h')
        
        if container_width > container_height:
            is_horizontal = True # container is horizontal
        else:
            is_horizontal = False
        
        if is_horizontal:
            container_width, container_height = container_height, container_width
        
        scale_x = screen_width / container_width
        scale_y = screen_height / container_height
        x_scaled = int(x * scale_x)
        y_scaled = int(y * scale_y)
        return x_scaled, y_scaled


def start():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", 
                        "--serial",
                        required=True,
                        help="device serial number")
    parser.add_argument("-p",
                        "--port",
                        type=int,
                        default=18080,
                        help="listen port")

    args = parser.parse_args()
        
    dev = HmDevice(args.serial)
    MJPEGHandler.CAP_READER = dev.cap_reader
    MiniTouchWSHandler.DEVICE = dev


    app = tornado.web.Application([
        (r"/", MainHandler),
        (r"/minitouch", MiniTouchWSHandler),
        (r"/mjpeg", MJPEGHandler),
    ], debug=True, template_path=os.path.join(os.path.dirname(__file__), "templates"))
    app.listen(args.port)

    enable_pretty_logging()
    tornado.ioloop.IOLoop.current().start()
    
if __name__ == "__main__":
    start()