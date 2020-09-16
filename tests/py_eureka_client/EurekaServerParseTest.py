# encoding: utf-8

import unittest

import py_eureka_client.logger as logger
from py_eureka_client.eureka_client import EurekaServer


class TestEurekaServer(unittest.TestCase):

    def __init__(self, methodName):
        super().__init__(methodName)
        logger.set_level("DEBUG")

    def test_init_eureka_server(self):
        es = EurekaServer(eureka_servers="https://a@10.0.2.16:8761/eureka,https://10.0.2.16:8762",
                          eureka_basic_auth_user="keijack", eureka_basic_auth_password="!@#qwe", zone="zone1")
        print(es.servers)

    def test_init_eureka_dns(self):
        es = EurekaServer(eureka_domain="keijack.com", eureka_basic_auth_user="keijack",
                          eureka_basic_auth_password="!@#qwe", region="dev", zone="zone1")
        print(es.servers_not_in_zone)

    def test_init_availability_zones(self):
        es = EurekaServer(eureka_availability_zones={"zone1": ["https://myec2.com", "myec1.com"], "zone2": "myzone2.com, myzone22.com"})
        print(es.servers)
