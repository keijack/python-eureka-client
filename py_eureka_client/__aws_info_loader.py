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
import py_eureka_client.http_client as http_client
from py_eureka_client.logger import get_logger

_logger = get_logger("aws_info_loader")

_CONNECTIVITY_TEST_TIMES = 5
_AWS_METADATA_SERVICE_IP = "169.254.169.254"
_AWS_METADATA_SERVICE_URL = "http://%s/latest/" % _AWS_METADATA_SERVICE_IP


class AmazonInfo(object):

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
                _logger.debug("Try amazon metadata services connectivity fail, retry (%d/%d)" % (idx, _CONNECTIVITY_TEST_TIMES))
                time.sleep(1)
        _logger.warn("Cannot connect to amazon metadata services in address [%s]" % _AWS_METADATA_SERVICE_IP)
        return False

    def get_ec2_metadata(self, meta_path, default_value=""):
        if not self.__can_access:
            _logger.warn("Cannot connect to amazon metadata services in address [%s], return default value. " % _AWS_METADATA_SERVICE_IP)
            return default_value
        try:
            return http_client.load(_AWS_METADATA_SERVICE_URL + "meta-data/" + meta_path)
        except Exception:
            _logger.exception("error when loading metadata from aws %s" % meta_path)
            return default_value

    def get_instance_identity_document(self, default_value={}):
        if not self.__can_access:
            _logger.warn("Cannot connect to amazon metadata services in address [%s], return default value. " % _AWS_METADATA_SERVICE_IP)
            return default_value
        try:
            doc = http_client.load(_AWS_METADATA_SERVICE_URL + "dynamic/instance-identity/document")
            return json.loads(doc)
        except Exception:
            _logger.exception("error when loading dynamic instance identity document from aws")
            return default_value
