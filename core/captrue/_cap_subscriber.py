#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# require: python >= 3.8

from logzero import logger
import queue

class CapSubscriber:
    
    def __init__(self):
        self._frame_queue = queue.Queue(maxsize=2)
        self._last_frame = None

    def release(self):
        pass

    def on_capture(self, frames):
        try:
            if self._frame_queue.full():
                self._frame_queue.get_nowait()
            # get encoded frame
            self._frame_queue.put_nowait(frames[1])
        except Exception as e:
            logger.exception(e)

    def on_start(self):
        pass
    
    def on_stop(self):
        self.release()
    
    def on_error(self, error):
        self.release()
        
    def get_content(self):
        frame = self._frame_queue.get_nowait()
        if frame is not None:
            self._last_frame = frame
        return self._last_frame
    
                