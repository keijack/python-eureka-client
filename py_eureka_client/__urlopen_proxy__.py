# -*- coding: utf-8 -*-
import socket
import re
import base64
import gzip

try:
    import urllib.request as urllib2
    from urllib.error import HTTPError
    from urllib.error import URLError
except ImportError:
    import urllib2
    from urllib2 import HTTPError
    from urllib2 import URLError
    from StringIO import StringIO

_URL_REGEX = re.compile(
    r'^(?:http)s?://'  # http:// or https://
    r'(([A-Z0-9_~!.%]+):([A-Z0-9_~!.%]+)@)?'  # basic authentication -> username:password@
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
    r'(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)|'  # domain name without `.`
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)


def get_url_and_basic_auth(addr_url):
    addr = addr_url

    match_obj = _URL_REGEX.match(addr)
    groups = match_obj.groups()
    if(groups[0] is not None):
        addr = addr.replace(groups[0], "")
        user_name = groups[1]
        user_psw = groups[2]
        ori_auth = ("%s:%s" % (user_name, user_psw)).encode()
        auth_str = base64.standard_b64encode(ori_auth).decode()
        return (addr, auth_str)
    else:
        return (addr, None)


class Request(urllib2.Request, object):

    def __init__(self, url, data=None, headers={},
                 origin_req_host=None, unverifiable=False,
                 method=None):
        url_match = _URL_REGEX.match(url)
        if url_match is None:
            raise URLError("Unvalid URL")
        url_obj = get_url_and_basic_auth(url)
        url_addr = url_obj[0]
        url_auth = url_obj[1]
        try:
            super(Request, self).__init__(url_addr, data=data, headers=headers,
                                          origin_req_host=origin_req_host, unverifiable=unverifiable,
                                          method=method)
        except TypeError:
            super(Request, self).__init__(url_addr, data=data, headers=headers,
                                          origin_req_host=origin_req_host, unverifiable=unverifiable)
            self.get_method = lambda: method if method is not None else "GET"
        if url_auth is not None:
            self.add_header('Authorization', 'Basic %s' % url_auth)


def urlopen(url, data=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
            cafile=None, capath=None, cadefault=False, context=None):
    if isinstance(url, urllib2.Request):
        request = url
    elif isinstance(url, str):
        request = Request(url)
    else:
        raise URLError("Unvalid URL")
    request.add_header("Accept-encoding", "gzip")
    res = urllib2.urlopen(request, data=data, timeout=timeout,
                          cafile=cafile, capath=capath, cadefault=cadefault, context=context)

    if res.info().get("Content-Encoding") == "gzip":
        try:
            # python2
            f = gzip.GzipFile(fileobj=StringIO(res.read()))
        except NameError:
            f = gzip.GzipFile(fileobj=res)
    else:
        f = res

    return f
