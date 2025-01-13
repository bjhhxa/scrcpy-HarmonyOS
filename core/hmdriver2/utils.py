#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# require: python >= 3.8

import time
import socket
from functools import wraps

shift_map = {
    '1': '!', '2': '@', '3': '#', '4': '$', '5': '%', '6': '^', '7': '&', '8': '*', '9': '(', '0': ')',
    '-': '_', '=': '+', '[': '{', ']': '}', '\\': '|', ';': ':', '\'': '"', ',': '<', '.': '>', '/': '?'
}

def translate_key(key, shift):
    # 对于字母，直接用大写表示 Shift 按下时的状态
    if key.isalpha():
        return key.upper() if shift else key.lower()
    # 对于其他字符，使用映射表
    elif shift and key in shift_map:
        return shift_map[key]
    else:
        return key

def delay(func):
    """
    After each UI operation, it is necessary to wait for a while to ensure the stability of the UI,
    so as not to affect the next UI operation.
    """
    DELAY_TIME = 0.6

    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        time.sleep(DELAY_TIME)
        return result
    return wrapper

class FreePort:
    def __init__(self):
        self._start = 30000
        self._end = 40000
        self._now = self._start - 1

    def get(self) -> int:
        while True:
            self._now += 1
            if self._now > self._end:
                self._now = self._start
            if not self.is_port_in_use(self._now):
                return self._now

    @staticmethod
    def is_port_in_use(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0