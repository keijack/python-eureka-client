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
import netifaces
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

def get_ip_and_host():
    if_list = netifaces.interfaces()
    ip = ""
    host = ""
    for if_name in if_list:
        ifaddr = netifaces.ifaddresses(if_name)
        if 2 in ifaddr:
            _ip = ifaddr[2][0]["addr"]
            if _ip != "127.0.0.1":
                ip = _ip
                host = get_host_by_ip(ip)
                break

    if not ip:
        host = socket.gethostname()
        ip = socket.gethostbyname(host)

    return ip, host
