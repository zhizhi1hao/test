#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
import serial
import minimalmodbus
import time
from datetime import datetime


class TemperatureHumiditySensor:
    def __init__(self, port, slave_address, baudrate=9600, parity=serial.PARITY_NONE,
                 stopbits=1, bytesize=8, timeout=1):
        """
        初始化Modbus RTU温湿度传感器

        参数:
            port: 串口设备路径 (如 '/dev/ttyUSB0')
            slave_address: 从站地址 (通常为1)
            baudrate: 波特率 (默认9600)
            parity: 奇偶校验 (默认无)
            stopbits: 停止位 (默认1)
            bytesize: 数据位 (默认8)
            timeout: 超时时间 (秒)
        """
        self.port = port
        self.slave_address = slave_address
        self.baudrate = baudrate
        self.parity = parity
        self.stopbits = stopbits
        self.bytesize = bytesize
        self.timeout = timeout

        # 初始化Modbus仪器
        try:
            self.instrument = minimalmodbus.Instrument(port, slave_address)
            self.instrument.serial.baudrate = baudrate
            self.instrument.serial.parity = parity
            self.instrument.serial.stopbits = stopbits
            self.instrument.serial.bytesize = bytesize
            self.instrument.serial.timeout = timeout
            self.instrument.mode = minimalmodbus.MODE_RTU
            print(f"成功初始化Modbus RTU传感器在端口 {port}")
        except Exception as e:
            print(f"初始化传感器失败: {e}")
            raise

    def read_temperature_humidity(self, temperature_register=0, humidity_register=1):
        """
        读取温度和湿度值

        参数:
            temperature_register: 温度寄存器地址 (根据传感器手册)
            humidity_register: 湿度寄存器地址 (根据传感器手册)

        返回:
            包含温度和湿度的字典，单位分别为摄氏度和百分比
        """
        try:
            # 读取温度 (通常寄存器中存储的值需要除以10或100得到实际值)
            temperature_raw = self.instrument.read_register(40003, 1)
            temperature = temperature_raw / 1000.0  # 根据传感器手册调整除数

            # 读取湿度
            humidity_raw = self.instrument.read_register(4000, 1)
            humidity = humidity_raw / 1000.0  # 根据传感器手册调整除数

            # 读取湿度
            humidity_fire = self.instrument.read_register(2, 1)
            fire = humidity_fire # 根据传感器手册调整除数

            return {
                'temperature': temperature,
                'humidity': humidity,
                'fire': fire,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            print(f"读取传感器数据失败: {e}")
            return None

    def close(self):
        """关闭串口连接"""
        if hasattr(self, 'instrument') and self.instrument.serial.is_open:
            self.instrument.serial.close()
            print("串口连接已关闭")


def main():
    # 配置参数 - 请根据您的实际硬件调整这些值
    SERIAL_PORT = '/dev/ttyS1'  # 串口设备路径
    SLAVE_ADDRESS = 3  # 从站地址
    BAUD_RATE = 9600  # 波特率
    POLL_INTERVAL = 5  # 采集间隔(秒)

    # 创建传感器实例
    try:
        sensor = TemperatureHumiditySensor(
            port=SERIAL_PORT,
            slave_address=SLAVE_ADDRESS,
            baudrate=BAUD_RATE
        )
    except Exception as e:
        print(f"无法初始化传感器: {e}")
        return

        # 使用运行标志控制循环
    running = True

    def signal_handler(signum, frame):
        nonlocal running
        print("接收到停止信号，正在关闭...")
        running = False
        # 注册信号处理

    import signal
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # kill命令

    try:
        while running:
            data = sensor.read_temperature_humidity()

            if data:
                print(f"温度: {data['temperature']:.1f}°C, 湿度: {data['humidity']:.1f}%, 火焰: {data['fire']:.1f}")
            else:
                print("未能读取到有效数据")

            # 使用更优雅的等待方式
            for _ in range(POLL_INTERVAL * 10):
                if not running:
                    break
                time.sleep(0.1)

    except Exception as e:
        print(f"程序运行出错: {e}")
    finally:
        sensor.close()
        print("传感器采集程序已正常退出")


if __name__ == "__main__":
    main()