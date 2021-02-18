# -*- coding: utf-8 -*-

"""
Copyright (c) 2018 Keijack Wu

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import socket
from typing import Tuple
from ifaddr import get_adapters
import ipaddress
from py_eureka_client.logger import get_logger

_logger = get_logger("netint_utils")


def get_host_by_ip(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except:
        _logger.warn("Error when getting host by ip", exc_info=True)
        return ip


def get_ip_by_host(host):
    try:
        return socket.gethostbyname(host)
    except:
        _logger.warn("Error when getting ip by host", exc_info=True)
        return host


def get_first_non_loopback_ip(network: str = "") -> str:
    adapters = get_adapters()
    for adapter in adapters:
        for iface in adapter.ips:
            if iface.is_IPv4:
                _ip = iface.ip
                if network:
                    if ipaddress.ip_address(_ip) in ipaddress.ip_network(network):
                        return _ip
                elif _ip != "127.0.0.1":
                    return _ip
    return ""


def get_ip_and_host(network: str = "") -> Tuple[str, str]:
    ip = get_first_non_loopback_ip(network=network)
    if not ip:
        host = socket.gethostname()
        ip = socket.gethostbyname(host)
    else:
        host = get_host_by_ip(ip)

    return ip, host
