#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# require: python >= 3.8

class HdcError(Exception):
    pass

class InvokeHypiumError(Exception):
    pass

class InvokeCaptures(Exception):
    pass

class ScreenCaptureError(Exception):
    pass

class DeviceNotFoundError(Exception):
    pass

class InjectGestureError(Exception):
    pass