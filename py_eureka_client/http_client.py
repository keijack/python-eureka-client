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

import re
import base64
import gzip
from typing import Union

import urllib.request
import urllib.error


class HTTPError(urllib.error.HTTPError):
    pass


class URLError(urllib.error.URLError):
    pass


"""
Default encoding
"""
_DEFAULT_ENCODING = "utf-8"

_URL_REGEX = re.compile(
    r'^((?:http)s?)://'  # http:// or https://
    # basic authentication -> username:password@
    r'(([A-Z0-9-_~!.%]+):([A-Z0-9-_~!.%]+)@)?'
    # domain...
    r'((?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
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
            ori_auth = f"{m.group(3)}:{m.group(4)}".encode()
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
        raise URLError(f"url[{url}] is not a valid url.")


class HttpRequest:

    def __init__(self, url, headers={}, method=None):
        url_match = _URL_REGEX.match(url)
        if url_match is None:
            raise URLError("Unvalid URL")
        url_obj = parse_url(url)
        url_addr = url_obj["url"]
        url_auth = url_obj["auth"]

        self.url = url_addr
        self.headers = headers or {}
        self.method = method

        if url_auth is not None:
            self.headers['Authorization'] = f'Basic {url_auth}'

    def add_header(self, key: str, value: str):
        self.headers[key] = value

    def _to_urllib_request(self):
        return urllib.request.Request(self.url, headers=self.headers, method=self.method)


class HttpResponse:

    def __init__(self, raw_response=None) -> None:
        self.raw_response = raw_response
        self.__body_read = False
        self.__body_text = ''

    def _read_body(self):
        res = self.raw_response
        if res.info().get("Content-Encoding") == "gzip":
            f = gzip.GzipFile(fileobj=res)
        else:
            f = res
        body_text = f.read().decode(_DEFAULT_ENCODING)
        f.close()
        return body_text

    @property
    def body_text(self):
        if not self.__body_read:
            self.__body_text = self._read_body()
            self.__body_read = True
        return self.__body_text

    @body_text.setter
    def body_text(self, val):
        self.__body_text = val
        self.__body_read = True


class HttpClient:

    async def urlopen(self, request: Union[str, HttpRequest] = None,
                      data: bytes = None, timeout: float = None) -> HttpResponse:
        if isinstance(request, HttpRequest):
            req = request
        elif isinstance(request, str):
            req = HttpRequest(request)
        else:
            raise URLError("Unvalid URL")

        res = urllib.request.urlopen(req._to_urllib_request(), data=data, timeout=timeout)
        return HttpResponse(res)


http_client = HttpClient()


def set_http_client(client: HttpClient) -> None:
    assert isinstance(client, HttpClient)
    global http_client
    http_client = client
