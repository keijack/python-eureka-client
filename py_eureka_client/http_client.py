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
import re
import base64
import gzip
import ssl
from typing import Union

import urllib.request
from http.client import HTTPResponse
from urllib.error import HTTPError
from urllib.error import URLError


"""
Default encoding
"""
_DEFAULT_ENCODING = "utf-8"

_URL_REGEX = re.compile(
    r'^((?:http)s?)://'  # http:// or https://
    r'(([A-Z0-9_~!.%]+):([A-Z0-9_~!.%]+)@)?'  # basic authentication -> username:password@
    r'((?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
    r'(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)|'  # domain name without `.`
    r"(?:\[((?:[A-F0-9]{1,4}:){7}[A-F0-9]{1,4})\])|"  # ipv6
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
    r'(?::(\d+))?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)


def parse_url(url):
    m = _URL_REGEX.match(url)
    if m:
        addr = url
        if m.group(2) is not None:
            addr = addr.replace(m.group(2), "")
            ori_auth = ("%s:%s" % (m.group(3), m.group(4))).encode()
            auth_str = base64.standard_b64encode(ori_auth).decode()
        else:
            auth_str = None
        return {
            "url": addr,
            "auth": auth_str,
            "schema": m.group(1),
            "host": m.group(5),
            "ipv6": m.group(6),
            "port": int(m.group(7)) if m.group(7) is not None else None
        }
    else:
        raise URLError("url[%s] is not a valid url." % url)


class Request(urllib.request.Request):

    def __init__(self, url, data=None, headers={},
                 origin_req_host=None, unverifiable=False,
                 method=None):
        url_match = _URL_REGEX.match(url)
        if url_match is None:
            raise URLError("Unvalid URL")
        url_obj = parse_url(url)
        url_addr = url_obj["url"]
        url_auth = url_obj["auth"]

        super().__init__(url_addr, data=data, headers=headers,
                         origin_req_host=origin_req_host, unverifiable=unverifiable,
                         method=method)

        if url_auth is not None:
            self.add_header('Authorization', 'Basic %s' % url_auth)


class HttpClient:

    def __init__(self, request: Union[str, urllib.request.Request] = None,
                 data: bytes = None, timeout: float = socket._GLOBAL_DEFAULT_TIMEOUT,
                 cafile: str = None, capath: str = None, cadefault: bool = False, context: ssl.SSLContext = None):
        self.request = request
        self.data = data
        self.timeout = timeout
        self.cafile = cafile
        self.capath = capath
        self.cadefault = cadefault
        self.context = context


    def urlopen(self):
        return urllib.request.urlopen(self.request, data=self.data, timeout=self.timeout,
                               cafile=self.cafile, capath=self.capath,
                               cadefault=self.cadefault, context=self.context)

    def read_response_body(self, res) -> str:
        if res.info().get("Content-Encoding") == "gzip":
            f = gzip.GzipFile(fileobj=res)
        else:
            f = res

        txt = f.read().decode(_DEFAULT_ENCODING)
        f.close()
        return txt


__HTTP_CLIENT_CLASS__ = HttpClient


def set_http_client_class(clz: HttpClient) -> None:
    assert issubclass(clz, HttpClient)
    global __HTTP_CLIENT_CLASS__
    __HTTP_CLIENT_CLASS__ = clz


def load(url, data: bytes = None, timeout: float = socket._GLOBAL_DEFAULT_TIMEOUT,
         cafile: str = None, capath: str = None, cadefault: bool = False, context: ssl.SSLContext = None):
    if isinstance(url, urllib.request.Request):
        request = url
    elif isinstance(url, str):
        request = Request(url)
    else:
        raise URLError("Unvalid URL")
    request.add_header("Accept-encoding", "gzip")
    http_cli = __HTTP_CLIENT_CLASS__(request=request, data=data, timeout=timeout,
                                cafile=cafile, capath=capath, cadefault=cadefault, context=context)
    res = http_cli.urlopen()
    txt = http_cli.read_response_body(res)
    return txt, res
