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

try:
    import dns.resolver
    no_dnspython = False
except (ModuleNotFoundError, NameError):
    no_dnspython = True
import subprocess

from py_eureka_client.logger import get_logger

_logger = get_logger("dns_txt_resolver")


def _get_txt_dns_record_from_lib(domain):
    try:
        records = dns.resolver.resolve(domain, 'TXT')
    except AttributeError:
        records = dns.resolver.query(domain, 'TXT')
    if len(records):
        return str(records[0]).replace('"', "").split(' ')


def _get_txt_dns_record_from_cmd(domain):
    cmd = ["host", "-t", "TXT", domain]
    out = subprocess.check_output(cmd)
    out = str(out.decode("UTF-8"))
    pre = "%s descriptive text " % domain
    if not out.startswith(pre):
        raise subprocess.SubprocessError("Cannot load text record from domain %s" % domain)
    return out.replace(pre, "").replace("\n", "").replace('"', "").split(' ')


def get_txt_dns_record(domain):
    if no_dnspython:
        _logger.info("Cannot find dnspython module, try to use host command to resovle domain [%s]" % domain)
        return _get_txt_dns_record_from_cmd(domain)
    else:
        return _get_txt_dns_record_from_lib(domain)
