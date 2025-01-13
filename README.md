# 简介

项目基于[鸿蒙Uitest协议](/docs/DEVELOP.md)为`HarmonyOS NEXT`设备提供了一种远程投屏及实时控制的解决方案。


## 功能

- 实时投屏
- 远程控制
- 屏幕录制

## 安装及使用

1. 配置鸿蒙HDC环境，具体步骤请参考[官方文档](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides-V13/ide-command-line-building-app-V13#section6767112163710)。
2. 克隆项目到本地：
   ```
   git clone https://github.com/bjhhxa/scrcpy-HarmonyOS.git
   ```
3. 安装依赖：
   ```
   pip install -r requirements.txt
   ```

4. 通过USB连接鸿蒙设备，并弃用设备的USB调试功能。
5. 使用HDC工具连接设备，获取设备的设备序列号。
   ```
   hdc list targtes
   ```
5. 运行项目：
   ```
   python example.py --serial <设备序列号> --port <服务端口号>
   ```
6. 在电脑上打开浏览器，访问`http://localhost:<服务端口号>`，即可开始使用。


## 致谢

感谢以下项目对本项目的贡献：

- [awesome-hdc](https://github.com/codematrixer/awesome-hdc)
- [HmDriver2](https://github.com/codematrixer/hmdriver2)

## 免责声明

本项目仅供学习和研究使用，不得用于任何商业用途。作者不对因使用本项目而造成的任何损失负责。