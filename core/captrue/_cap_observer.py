#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# require: python >= 3.8

import cv2
import typing
import threading

from logzero import logger
from datetime import datetime
import numpy as np
from multiprocessing.pool import Pool

from core.hmdriver2 import ScreenCaptureError
from core.hmdriver2 import HmDriver
from ._cap_subscriber import CapSubscriber


def _capture_reader(thiz):
    """Capture screen frames and save current frames."""

    # JPEG start and end markers.
    start_flag = b'\xff\xd8'
    end_flag = b'\xff\xd9'
    buffer = bytearray()
    while not thiz.stop_event.is_set():
        try:
            buffer += thiz._recv_msg(4096 * 1024, decode=False, print=False)
        except Exception as e:
            print(f"Error receiving data: {e}")
            break

        start_idx = buffer.find(start_flag)
        end_idx = buffer.find(end_flag)
        while start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            # Extract one JPEG image
            jpeg_image: bytearray = buffer[start_idx:end_idx + 2]
            buffer = buffer[end_idx + 2:]
            # Search for the next JPEG image in the buffer
            start_idx = buffer.find(start_flag)
            end_idx = buffer.find(end_flag)
            yield jpeg_image
            
    logger.debug("_capture_reader exit")
    
def _captrue_factory(jpeg_image):
    """decode and resize jpeg image"""
    try:
        # Decode the JPEG image
        frame_tmp = cv2.imdecode(np.frombuffer(jpeg_image, np.uint8), cv2.IMREAD_COLOR)
        # Resize the image to 40% of its original size
        frame_decoded = cv2.resize(frame_tmp, (0, 0), fx=0.3, fy=0.3, interpolation=cv2.INTER_AREA)
        # Set the JPEG compression quality to 70%
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 50]
        _, frame_encoded = cv2.imencode('.jpg', frame_decoded, encode_params)
        # Return the decoded and encoded frames
        return (frame_decoded, frame_encoded)
    except Exception as e:
        logger.error(f"Error decoding jpeg image: {e}")
        return None
    

class CapObserver(HmDriver):
    def __init__(self, serial: str):
        super().__init__(serial)

        self.video_path = None
        self.subscribers: typing.List[CapSubscriber] = []
        self.threads: typing.List[threading.Thread] = []
        self.stop_event = threading.Event()
        
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        
    def release(self):
        self.stop()
        self.subscribers.clear()
        super().release()

    def _send_msg(self, api: str, args: list):
        """Send an message to the server.

        Args:
            api (str): API name.
            args (list): API arguments.
        """
        _msg = {
            "module": "com.ohos.devicetest.hypiumApiHelper",
            "method": "Captures",
            "params": {
                "api": api,
                "args": args
            },
            "request_id": datetime.now().strftime("%Y%m%d%H%M%S%f")
        }
        super()._send_msg(_msg)

    def _on_capture(self, frames):
        """Notify all subscribers of the new screen capture."""
        for subscriber in self.subscribers:
            subscriber.on_capture(frames)

    def start(self):
        """Start screen capture.

        Args:
            callback (function): Callback function to process screen frames.

        Raises:
            ScreenCaptureError: Failed to start device screen capture.

        Returns:
            _type_: _description_
        """
        logger.info("Start Captures Client connection")
        self._connect_sock()
        self._send_msg("startCaptureScreen", [])

        reply: str = self._recv_msg(1024, decode=True, print=False)
        if "true" in reply:
            def _on_capture(thiz):
                logger.debug("captrue loop start")
                with Pool() as pool:
                    for frames in pool.imap(_captrue_factory, _capture_reader(thiz)):
                        if frames is not None:
                            thiz._on_capture(frames)
                logger.debug("captrue loop exit")
            
            
            # Start a new thread to process screen frames
            work_th = threading.Thread(target=_on_capture, args=(self,))
            work_th.daemon = True
            work_th.start()
            self.threads.append(work_th)
            
            # notify all subscribers that screen capture has started
            for subscriber in self.subscribers:
                    subscriber.on_start()
        else:
            for subscriber in self.subscribers:
                    subscriber.on_error("Failed to start device screen capture.")
            raise ScreenCaptureError("Failed to start device screen capture.")

        return self

    def stop(self):
        """Stop screen capture."""
        try:
            self.stop_event.set()
            for t in self.threads:
                t.join()

            self._send_msg("stopCaptureScreen", [])
            self._recv_msg(1024, decode=True, print=False)
            self.release()
            # notify all subscribers that screen capture has stopped            
            for subscriber in self.subscribers:
                subscriber.on_stop()
        except Exception as e:
            for subscriber in self.subscribers:
                    subscriber.on_error("Failed to stop device screen capture.")
            logger.error(f"An error occurred: {e}")

    def subscribe(self, subscriber: CapSubscriber):
        """Subscribe to screen capture.

        Args:
            subscriber (CaptureSubscriber): Subscriber to receive screen frames.
        """
        self.subscribers.append(subscriber)
        
    def unsubscribe(self, subscriber: CapSubscriber):
        """Unsubscribe from screen capture.

        Args:
            subscriber (CaptureSubscriber): Subscriber to unsubscribe.
        """
        self.subscribers.remove(subscriber)