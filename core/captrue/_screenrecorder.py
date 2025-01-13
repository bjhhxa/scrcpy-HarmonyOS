#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# require: python >= 3.8

import cv2
import queue
import threading
import time

from logzero import logger
from pathlib import Path
from ._cap_subscriber import CapSubscriber

class ScreenRecorder(CapSubscriber):
    def __init__(self, video_path: str):
        self._video_path = video_path
        self.cv2_instance = None
        self.stop_event = threading.Event()
        self._frame_queue = queue.Queue()
        self._record_th = None
        self._is_recording = False
    
    @property
    def is_recording(self):
        return self.cv2_instance is not None
    
    @property
    def video_path(self):
        return self._video_path
    
    def start(self):
        try:
            Path(self._video_path).parent.mkdir(parents=True, exist_ok=True)
            self._record_th = threading.Thread(target=self._video_writer, args=(self._video_path,))
            self._record_th.daemon = True
            self._record_th.start()
            self._is_recording = True
        except Exception as e:
            logger.exception(e)

    def stop(self):
        self.release()

    def release(self):
        self._is_recording = False
        self.stop_event.set()
        if self._record_th is not None:
            self._record_th.join()

        if self.cv2_instance is not None:
            self.cv2_instance.release()
            self.cv2_instance = None
        super().release()
    
    def on_capture(self, frames):
        """Write frames to video file."""
        if self._is_recording is False:
            return        
        # super().on_capture(jpeg_frame)
        self._frame_queue.put_nowait(frames[0])
        
    def _video_writer(self):        
        while not self.stop_event.is_set():
            if not self._frame_queue.empty():
                frame = self._frame_queue.get(timeout=0.1)
                if frame is not None:
                    if cv2_instance is None:
                        height, width = frame.shape[:2]
                        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                        cv2_instance = cv2.VideoWriter(self._video_path, fourcc, 10, (width, height))
                    cv2_instance.write(frame)    
            else:
                time.sleep(0.01)
