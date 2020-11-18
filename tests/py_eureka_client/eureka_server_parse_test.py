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

import unittest

import py_eureka_client.logger as logger
from py_eureka_client.eureka_client import EurekaServerConf

logger.set_level("DEBUG")

class TestEurekaServer(unittest.TestCase):

    def test_init_eureka_server(self):
        es = EurekaServerConf(eureka_server="https://a@10.0.2.16:8761/eureka,https://10.0.2.16:8762",
                          eureka_basic_auth_user="keijack", eureka_basic_auth_password="!@#qwe", zone="zone1")
        print(es.servers)

    def test_init_eureka_dns(self):
        es = EurekaServerConf(eureka_domain="keijack.com", eureka_basic_auth_user="keijack",
                          eureka_basic_auth_password="!@#qwe", region="dev", zone="zone1")
        print(es.servers_not_in_zone)

    def test_init_availability_zones(self):
        es = EurekaServerConf(eureka_availability_zones={"zone1": ["https://myec2.com", "myec1.com"], "zone2": "myzone2.com, myzone22.com"})
        print(es.servers)
