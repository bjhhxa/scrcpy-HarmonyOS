#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# require: python >= 3.8

import json
import uuid

from logzero import logger
from typing import Type, Any, Tuple, Dict, Union, List
from functools import cached_property # python3.8+

from core.hmdriver2.protocol import HypiumResponse, CommandResult, KeyCode, DisplayRotation, DeviceInfo, Point
from core.hmdriver2.utils import delay
from core.hmdriver2._driver import HmDriver
from core.captrue import CapObserver, CapSubscriber, ScreenRecorder

class HmDevice:
    _instance: Dict = {}
    
    def __init__(self, serial: str):
        self.serial = serial
        self._driver = HmDriver(serial)
        self._cap_observer = CapObserver(serial)
        self._cap_subscriber = CapSubscriber()
        self.hdc = self._driver.hdc
        self._init_driver()

    def __new__(cls: Type[Any], serial: str) -> Any:
        """
        Ensure that only one instance of Driver exists per device serial number.
        """
        if serial not in cls._instance:
            cls._instance[serial] = super().__new__(cls)
        return cls._instance[serial]

    def __del__(self):
        if hasattr(self, '_driver') and self._driver:
            self._driver.release()
        if hasattr(self, '_cap_observer') and self._cap_observer:
            self._cap_observer.release()
    
    def _init_driver(self):
        """init driver"""
        self._driver.start()
        
        self._cap_observer.subscribe(self._cap_subscriber)
        self._cap_observer.start()
        logger.debug("_cap_observer started")
        
    def _invoke(self, api: str, args: List = []) -> HypiumResponse:
        """invoke api"""
        return self._driver.invoke(api, this="Driver#0", args=args)

    
    @delay
    def start_app(self, package_name: str, ability_name: str = "MainAbility"):
        """start app

        Args:
            package_name (str): _description_
            ability_name (str, optional): _description_. Defaults to "MainAbility".
        """
        self.hdc.start_app(package_name, ability_name)
        
    def stop_app(self, package_name: str):
        """stop app

        Args:
            package_name (str): _description_
        """
        self.hdc.stop_app(package_name)
        
    def force_start_app(self, package_name: str, ability_name: str = "MainAbility"):
        """force start app

        Args:
            package_name (str): _description_
            ability_name (str, optional): _description_. Defaults to "MainAbility".
        """
        self.go_home()
        self.stop_app(package_name)
        self.start_app(package_name, ability_name)
        
    def install_app(self, path: str):
        """install app

        Args:
            path (str): _description_
        """
        self.hdc.install(path)
        
    def uninstall_app(self, package_name: str):
        """uninstall app

        Args:
            package_name (str): _description_
        """
        self.hdc.uninstall(package_name)
        
    def dump_apps(self) -> List:
        """dump apps
        """
        return self.hdc.dump_apps()
    
    def has_app(self, pkg: str) -> bool:
        """check if app is installed

        Args:
            pkg (str): _description_

        Returns:
            bool: _description_
        """
        return self.hdc.has_app(pkg)
    
    def current_app(self) -> Tuple[str, str]:
        """get current app

        Returns:
            str: _description_
        """
        return self.hdc.current_app()
    
    def get_app_info(self, package_name: str) -> Dict:
        """
        Get detailed information about a specific application.

        Args:
            package_name (str): The package name of the application to retrieve information for.

        Returns:
            Dict: A dictionary containing the application information. If an error occurs during parsing,
                an empty dictionary is returned.
        """
        app_info = {}
        data: CommandResult = self.hdc.shell(f"bm dump -n {package_name}")
        output = data.output
        try:
            json_start = output.find("{")
            json_end = output.rfind("}") + 1
            json_output = output[json_start:json_end]

            app_info = json.loads(json_output)
        except Exception as e:
            logger.error(f"An error occurred:{e}")
        return app_info

    def start_screen_recorder(self, video_path: str):
        """start screen recorder

        Args:
            video_path (str): _description_
        """
        
        sr = ScreenRecorder(video_path)
        self._cap_observer.subscribe(sr)
        sr.start()
        return sr
        
        # self._screenrecorder.start(video_path)
        
    def stop_screen_recorder(self, sr):
        """stop screen recorder"""
        if sr is None:
            return
        sr.stop()
        self._cap_observer.unsubscribe(sr)
    
    @delay
    def go_back(self):
        self.hdc.send_key(KeyCode.BACK)

    @delay
    def go_home(self):
        self.hdc.send_key(KeyCode.HOME)
        
    @delay
    def press_key(self, key_code: Union[KeyCode, int]):
        """press key

        Args:
            key_code (Union[KeyCode, int]): _description_
        """
        self.hdc.send_key(key_code)
        
    @delay
    def press_key_ex(self, key_code: str):
        """press key

        Args:
            key_code (str): _description_
        """
        self.hdc.send_key_event(key_code)

    def screen_on(self):
        """screen on"""
        self.hdc.wakeup()
        
    def screen_off(self):
        """screen off
        """
        self.hdc.wakeup()
        self.press_key(KeyCode.POWER)
        
    @delay
    def unlock(self):
        """unlock screen"""
        self.screen_on()
        w, h = self.display_size
        self.swipe(0.5 * w, 0.8 * h, 0.5 * w, 0.2 * h, speed=6000)
        
    @delay
    def open_url(self, url: str, system_browser: bool = True):
        if system_browser:
            # Use the system browser
            self.hdc.shell(f"aa start -A ohos.want.action.viewData -e entity.system.browsable -U {url}")
        else:
            # Default method
            self.hdc.shell(f"aa start -U {url}")
            
    @delay
    def input_text(self, text: str):
        """
        Inputs text into the currently focused input field.

        Note: The input field must have focus before calling this method.

        Args:
            text (str): input value
        """
        return self._invoke("Driver.inputText", args=[{"x": 1, "y": 1}, text])


    @property
    def cap_reader(self) -> CapSubscriber:
        return self._cap_subscriber
    
    @cached_property
    def gesture(self):
        from core.hmdriver2._gesture import _Gesture
        return _Gesture(self)


    @cached_property
    def display_size(self) -> Tuple[int, int]:
        api = "Driver.getDisplaySize"
        resp: HypiumResponse = self._invoke(api)
        w, h = resp.result.get("x"), resp.result.get("y")
        return w, h
    
    @property
    def display_rotation(self) -> DisplayRotation:
        api = "Driver.getDisplayRotation"
        value = self._invoke(api).result
        return DisplayRotation.from_value(value)
    
    @cached_property
    def device_info(self) -> DeviceInfo:
        """
        Get detailed information about the device.

        Returns:
            DeviceInfo: An object containing various properties of the device.
        """
        hdc = self.hdc
        return DeviceInfo(
            productName=hdc.product_name(),
            model=hdc.model(),
            sdkVersion=hdc.sdk_version(),
            sysVersion=hdc.sys_version(),
            cpuAbi=hdc.cpu_abi(),
            wlanIp=hdc.wlan_ip(),
            displaySize=self.display_size,
            displayRotation=self.display_rotation
        )
    
    def set_display_rotation(self, rotation: DisplayRotation):
        """
        Sets the display rotation to the specified orientation.

        Args:
            rotation (DisplayRotation): display rotation.
        """
        api = "Driver.setDisplayRotation"
        self._invoke(api, args=[rotation.value])
    
    def pull_file(self, rpath: str, lpath: str):
        """
        Pull a file from the device to the local machine.

        Args:
            rpath (str): The remote path of the file on the device.
            lpath (str): The local path where the file should be saved.
        """
        self.hdc.recv_file(rpath, lpath)

    def push_file(self, lpath: str, rpath: str):
        """
        Push a file from the local machine to the device.

        Args:
            lpath (str): The local path of the file.
            rpath (str): The remote path where the file should be saved on the device.
        """
        self.hdc.send_file(lpath, rpath)
        
    def screenshot(self, path: str) -> str:
        """
        Take a screenshot of the device display.

        Args:
            path (str): The local path to save the screenshot.

        Returns:
            str: The path where the screenshot is saved.
        """
        _uuid = uuid.uuid4().hex
        _tmp_path = f"/data/local/tmp/_tmp_{_uuid}.jpeg"
        self.shell(f"snapshot_display -f {_tmp_path}")
        self.pull_file(_tmp_path, path)
        self.shell(f"rm -rf {_tmp_path}")  # remove local path
        return path

    def shell(self, cmd) -> CommandResult:
        """execute shell command on device

        Args:
            cmd (_type_): command

        Returns:
            CommandResult: _description_
        """
        return self.hdc.shell(cmd)
    
    def dump_hierarchy(self) -> Dict:
        """
        Dump the UI hierarchy of the device screen.

        Returns:
            Dict: The dumped UI hierarchy as a dictionary.
        """
        # return self._client.invoke_captures("captureLayout").result
        return self.hdc.dump_hierarchy()

    def _to_abs_pos(self, x: Union[int, float], y: Union[int, float], percent: bool = True) -> Point:
        """
        Convert percentages to absolute screen coordinates.

        Args:
            x (Union[int, float]): X coordinate as a percentage or absolute value.
            y (Union[int, float]): Y coordinate as a percentage or absolute value.

        Returns:
            Point: A Point object with absolute screen coordinates.
        """
        assert x >= 0
        assert y >= 0

        w, h = self.display_size

        if percent:
            if x < 1:
                x = int(w * x)
            if y < 1:
                y = int(h * y)
        return Point(int(x), int(y))

    @delay
    def click(self, x: Union[int, float], y: Union[int, float]):

        # self.hdc.tap(point.x, point.y)
        point = self._to_abs_pos(x, y)
        api = "Driver.click"
        self._invoke(api, args=[point.x, point.y])

    @delay
    def double_click(self, x: Union[int, float], y: Union[int, float]):
        point = self._to_abs_pos(x, y)
        api = "Driver.doubleClick"
        self._invoke(api, args=[point.x, point.y])

    @delay
    def long_click(self, x: Union[int, float], y: Union[int, float]):
        point = self._to_abs_pos(x, y)
        api = "Driver.longClick"
        self._invoke(api, args=[point.x, point.y])

    @delay
    def swipe(self, x1, y1, x2, y2, speed=2000):
        """
        Perform a swipe action on the device screen.

        Args:
            x1 (float): The start X coordinate as a percentage or absolute value.
            y1 (float): The start Y coordinate as a percentage or absolute value.
            x2 (float): The end X coordinate as a percentage or absolute value.
            y2 (float): The end Y coordinate as a percentage or absolute value.
            speed (int, optional): The swipe speed in pixels per second. Default is 2000. Range: 200-40000,
            If not within the range, set to default value of 2000.
        """

        point1 = self._to_abs_pos(x1, y1)
        point2 = self._to_abs_pos(x2, y2)

        if speed < 200 or speed > 40000:
            logger.warning("`speed` is not in the range[200-40000], Set to default value of 2000.")
            speed = 2000

        api = "Driver.swipe"
        self._invoke(api, args=[point1.x, point1.y, point2.x, point2.y, speed])

