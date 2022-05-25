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
import json
import time
from py_eureka_client.http_client import http_client
from py_eureka_client.logger import get_logger

_logger = get_logger("aws_info_loader")

_CONNECTIVITY_TEST_TIMES = 5
_AWS_METADATA_SERVICE_IP = "169.254.169.254"
_AWS_METADATA_SERVICE_URL = f"http://{_AWS_METADATA_SERVICE_IP}/latest/"


class AmazonInfo:

    def __init__(self):
        self.__can_access = self.__check_connectivity()

    def __check_connectivity(self):
        for i in range(_CONNECTIVITY_TEST_TIMES):
            try:
                s = socket.socket()
                s.connect((_AWS_METADATA_SERVICE_IP, 80))
                s.close()
                return True
            except socket.error:
                idx = i + 1
                _logger.debug(
                    f"Try amazon metadata services connectivity fail, retry ({idx}/{_CONNECTIVITY_TEST_TIMES})")
                time.sleep(1)
        _logger.warn(
            f"Cannot connect to amazon metadata services in address [{_AWS_METADATA_SERVICE_IP}]")
        return False

    async def get_ec2_metadata(self, meta_path, default_value="", ignore_error=False):
        if not self.__can_access:
            _logger.warn(
                f"Cannot connect to amazon metadata services in address [{_AWS_METADATA_SERVICE_IP}], return default value. ")
            return default_value
        try:
            res = await http_client.urlopen(f"{_AWS_METADATA_SERVICE_URL}meta-data/{meta_path}")
            return res.body_text
        except Exception:
            log_excep = _logger.debug if ignore_error else _logger.exception
            log_excep(f"error when loading metadata from aws {meta_path}")
            return default_value

    async def get_instance_identity_document(self, default_value={}):
        if not self.__can_access:
            _logger.warn(
                f"Cannot connect to amazon metadata services in address [{_AWS_METADATA_SERVICE_IP}], return default value. ")
            return default_value
        try:
            doc = await http_client.urlopen(f"{_AWS_METADATA_SERVICE_URL}dynamic/instance-identity/document")
            return json.loads(doc.body_text)
        except Exception:
            _logger.exception(
                "error when loading dynamic instance identity document from aws")
            return default_value
