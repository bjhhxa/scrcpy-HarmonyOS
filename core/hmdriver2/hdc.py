#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# require: python >= 3.8
# see: https://github.com/codematrixer/awesome-hdc  

import tempfile
import subprocess
import shlex
import json
import uuid
import re
from logzero import logger
from typing import Union, List, Tuple, Dict

from .exception import DeviceNotFoundError, HdcError
from .protocol import CommandResult, KeyCode, KeyMap
from .utils import FreePort

def _execute_command(cmdargs: Union[str, List[str]]) -> CommandResult:
    """execute a command

    Args:
        cmdargs (Union[str, List[str]]): _description_

    Returns:
        CommandResult: _description_
    """
    if isinstance(cmdargs, (list, tuple)):
        cmdline: str = ' '.join(list(map(shlex.quote, cmdargs)))
    elif isinstance(cmdargs, str):
        cmdline = cmdargs

    logger.debug(cmdline)
    try:
        process = subprocess.Popen(cmdline, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, shell=True)
        output, error = process.communicate()
        output = output.decode('utf-8')
        error = error.decode('utf-8')
        exit_code = process.returncode

        if 'error:' in output.lower() or '[fail]:' in output.lower():
            return CommandResult("", output, -1)

        return CommandResult(output, error, exit_code)
    except Exception as e:
        return CommandResult("", str(e), -1)


def list_targets() -> List[str]:
    """list all device status

    Returns:
        [str]: _description_
    """
    devices = []
    resp = _execute_command('hdc list targets')
    if resp.exit_code == 0 and resp.output:
        for line in resp.output.strip().splitlines():
            if line.__contains__('Empty'):
                continue
            devices.append(line.strip())
    
    if resp.exit_code != 0:
        raise HdcError("HDC error", "hdc list targets", resp.error)    
    
    return devices


class HdcWrapper:
    def __init__(self, serial: str) -> None:
        self.serial = serial
        if not self.is_online():
            raise DeviceNotFoundError(f"Device [{self.serial}] is not found")
        
    
    def is_online(self) -> bool:
        """check if device is online

        Returns:
            bool: true if device is online
        """
        _serials = list_targets()
        return True if self.serial in _serials else False
    
    
    def send_file(self, local_path: str, remote_path: str) -> CommandResult:
        """send file to device

        Args:    
            local_path (str): _description_
            remote_path (str): _description_

        Returns:
            CommandResult: _description_
        """
        result = _execute_command(f"hdc -t {self.serial} file send {local_path} {remote_path}")          
        if result.exit_code != 0:
            raise HdcError("HDC error", "hdc file send", result.error)
        return result
    
    def recv_file(self, remote_path: str, local_path: str) -> CommandResult:
        """receive file from device

        Args:
            remote_path (str): _description_
            local_path (str): _description_

        Returns:
            CommandResult: _description_
        """
        result = _execute_command(f"hdc -t {self.serial} file recv {remote_path} {local_path}")          
        if result.exit_code != 0:
            raise HdcError("HDC error", "hdc file recv", result.error)
        return result
    
    
    def screenshot(self, path: str) -> str:
        """take screenshot

        Args:
            path (str): _description_

        Returns:
            str: _description_
        """
        _uuid = uuid.uuid4().hex
        _tmp_path = f"/data/local/tmp/_tmp_{_uuid}.jpeg"
        self.shell(f"snapshot_display -f {_tmp_path}")
        self.recv_file(_tmp_path, path)
        self.shell(f"rm -rf {_tmp_path}")  # remove local path
        return path
    
    def shell(self, cmd: str) -> CommandResult:
        """execute shell command on device

        Args:
            cmd (str): _description_

        Returns:
            CommandResult: _description_
        """
        result = _execute_command(f"hdc -t {self.serial} shell {cmd}")          
        if result.exit_code != 0:
            raise HdcError("HDC error", "hdc shell", result.error)
        return result
    
    def install(self, src: str) -> CommandResult:
        """install apk on device

        Args:
            src (str): _description_

        Returns:
            CommandResult: _description_
        """
        quoted_path = shlex.quote(src)
        result = _execute_command(f"hdc -t {self.serial} install {src}")          
        if result.exit_code != 0:
            raise HdcError("HDC error", "hdc install", result.error)
        return result
    
    def uninstall(self, pkg: str) -> CommandResult:
        """uninstall apk on device

        Args:
            pkg (str): _description_

        Returns:
            CommandResult: _description_
        """
        result = _execute_command(f"hdc -t {self.serial} uninstall {pkg}")          
        if result.exit_code != 0:
            raise HdcError("HDC error", "hdc uninstall", result.error)
        return result
    
    
    def dump_apps(self) -> List[str]:
        """dump all installed apps

        Returns:
            List[str]: _description_
        """
        result = self.shell("bm dump -a")
        raw = result.output.strip().splitlines()
        return [item.strip() for item in raw]
    
    def has_app(self, pkg: str) -> bool:
        """check if app is installed

        Args:
            pkg (str): _description_

        Returns:
            bool: _description_
        """
        return True if pkg in self.dump_apps() else False
    
    def start_app(self, package_name: str, ability_name: str) -> CommandResult:
        """start app    

        Args:
            package_name (str): _description_
            ability_name (str): _description_

        Returns:
            CommandResult: _description_
        """
        result = self.shell(f"aa start -a {ability_name} -b {package_name}")
        if result.exit_code != 0:
            raise HdcError("HDC error", "hdc aa start", result.error)
        return result
        
    def stop_app(self, package_name: str) -> CommandResult:
        """stop app    

        Args:
            package_name (str): _description_

        Returns:
            CommandResult: _description_
        """
        result = self.shell(f"aa force-stop {package_name}")
        if result.exit_code != 0:
            raise HdcError("HDC error", "hdc aa stop", result.error)
        return result
    
    def current_app(self) -> Tuple[str, str]:
        """
        Get the current foreground application information.

        Returns:
            Tuple[str, str]: A tuple contain the package_name andpage_name of the foreground application.
                            If no foreground application is found, returns (None, None).
        """

        def __extract_info(output: str):
            results = []

            mission_blocks = re.findall(r'Mission ID #[\s\S]*?isKeepAlive: false\s*}', output)
            if not mission_blocks:
                return results

            for block in mission_blocks:
                if 'state #FOREGROUND' in block:
                    bundle_name_match = re.search(r'bundle name \[(.*?)\]', block)
                    main_name_match = re.search(r'main name \[(.*?)\]', block)
                    if bundle_name_match and main_name_match:
                        package_name = bundle_name_match.group(1)
                        page_name = main_name_match.group(1)
                        results.append((package_name, page_name))

            return results

        data: CommandResult = self.shell("aa dump -l")
        output = data.output
        results = __extract_info(output)
        return results[0] if results else (None, None)
    
    def forward_port(self, remote_port: int) -> int:
        """forward port

        Args:
            local_port (int): _description_
            remote_port (int): _description_

        Returns:
            CommandResult: _description_
        """
        lport: int = FreePort().get()
        result = _execute_command(f"hdc -t {self.serial} fport tcp:{lport} tcp:{remote_port}")
        if result.exit_code != 0:
            raise HdcError("HDC error", "hdc fport", result.error)
        return lport
        
    def rm_fport(self, local_port: int, remote_port: int) -> int:
        """remove forward port

        Args:
            local_port (int): _description_
            remote_port (int): _description_

        Returns:
            CommandResult: _description_
        """
        result = _execute_command(f"hdc -t {self.serial} fport rm {remote_port} {local_port}")
        if result.exit_code != 0:
            raise HdcError("HDC error", "hdc fport rm", result.error)
        return local_port
        
    def list_fports(self) -> List:
        """list all forward ports

        Returns:
            List: _description_
        """
        result = _execute_command(f"hdc -t {self.serial} fport ls")
        if result.exit_code != 0:
            raise HdcError("HDC forward list error", result.error)
        pattern = re.compile(r"tcp:\d+ tcp:\d+")
        return pattern.findall(result.output)

    def wakeup(self):
        """wakeup device"""
        self.shell("power-shell wakeup")
        
    def screen_state(self) -> str:
        """get screen state

        Returns:
            str: ["INACTIVE", "SLEEP, AWAKE"]
        """
        data = self.shell("hidumper -s PowerManagerService -a -s").output
        pattern = r"Current State:\s*(\w+)"
        match = re.search(pattern, data)
        
    def wlan_ip(self)  -> Union[str, None]:
        """get wlan ip  
        """
        data = self.shell("ifconfig").output
        matches = re.findall(r'inet addr:(?!127)(\d+\.\d+\.\d+\.\d+)', data)
        return matches[0] if matches else None

    def sys_version(self) -> str:
        """get system version

        Returns:    
            str: _description_
        """
        data = self.shell("param get const.product.software.version").output
        return self.__split_text(data)
        
        
    def sdk_version(self) -> str:
        """get sdk version

        Returns:    
            str: _description_
        """
        data = self.shell("param get const.ohos.apiversion").output
        return self.__split_text(data)
    
    def model(self) -> str:
        """get model

        Returns:    
            str: _description_
        """
        data = self.shell("param get const.product.model").output
        return self.__split_text(data)
    
    def brand(self) -> str:
        """get brand

        Returns:    
            str: _description_
        """    
        data = self.shell("param get const.product.brand").output
        return self.__split_text(data)
    
    
    def product_name(self) -> str:
        """get product name

        Returns:    
            str: _description_
        """
        data = self.shell("param get const.product.name").output
        return self.__split_text(data)
    
    def cpu_abi(self) -> str:
        """get cpu abi

        Returns:    
            str: _description_
        """
        data = self.shell("param get const.product.cpu.abilist").output
        return self.__split_text(data)
    
    def display_size(self) -> Tuple[int, int]:
        """get display size

        Returns:    
            Tuple[int, int]: _description_
        """
        data = self.shell("hidumper -s RenderService -a screen").output
        match = re.search(r'activeMode:\s*(\d+)x(\d+),\s*refreshrate=\d+', data)

        if match:
            w = int(match.group(1))
            h = int(match.group(2))
            return (w, h)
        return (0, 0)
    
    def send_key(self, key_code: Union[KeyCode, int]) -> None:
        if isinstance(key_code, KeyCode):
            key_code = key_code.value

        MAX = 3200
        if key_code > MAX:
            raise HdcError("Invalid HDC keycode")

        self.shell(f"uitest uiInput keyEvent {key_code}")
        
        
    def send_key_event(self, key: str):
        
        key_codes = KeyMap.get(key, None)
        if key_codes is None:
            return
        
        key_map = ""
        for key_code in key_codes:
            key_map += f"{key_code.value} "
        
        self.shell(f"uitest uiInput keyEvent {key_map}")

    def tap(self, x: int, y: int) -> None:
        self.shell(f"uitest uiInput click {x} {y}")

    def swipe(self, x1, y1, x2, y2, speed=1000):
        self.shell(f"uitest uiInput swipe {x1} {y1} {x2} {y2} {speed}")

    def input_text(self, x: int, y: int, text: str):
        self.shell(f"uitest uiInput inputText {x} {y} {text}")


    def dump_hierarchy(self) -> Dict:
        _tmp_path = f"/data/local/tmp/{self.serial}_tmp.json"
        self.shell(f"uitest dumpLayout -p {_tmp_path}")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
            path = f.name
            self.recv_file(_tmp_path, path)

            try:
                with open(path, 'r', encoding='utf8') as file:
                    data = json.load(file)
            except Exception as e:
                logger.error(f"Error loading JSON file: {e}")
                data = {}

            return data

    def __split_text(self, text: str) -> str:
        """split text

        Args:
            text (str): _description_

        Returns:
            str: _description_
        """
        return text.split("\n")[0].strip() if text else None
    