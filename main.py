#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import serial.tools.list_ports
def get_available_ports():
    """获取所有可用的串口列表"""
    ports = serial.tools.list_ports.comports()
    port_list = []

    for port, desc, hwid in sorted(ports):
        port_list.append({
            'port': port,
            'description': desc,
            'hardware_id': hwid
        })
        print(f"端口: {port}, 描述: {desc}, 硬件ID: {hwid}")

    return port_list


get_available_ports()