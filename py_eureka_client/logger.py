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

import sys
import queue
import logging
from logging import StreamHandler
from threading import Thread

_LOG_LEVEL_ = "INFO"
__loggers = {}
__cache_loggers = {}

__formatter_ = logging.Formatter(
    fmt='[%(asctime)s]-[%(name)s]-[line:%(lineno)d] -%(levelname)-4s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(__formatter_)
_handler.setLevel(_LOG_LEVEL_)

_handlers = []
_handlers.append(_handler)

_msg_cache = queue.Queue(10000)


class CachingLogger(logging.Logger):

    def _call_handlers(self, record):
        super(CachingLogger, self).callHandlers(record)

    def callHandlers(self, record):
        _msg_cache.put((self, record))


def set_level(level):
    global _LOG_LEVEL_
    lv = level.upper()
    if lv in ("DEBUG", "INFO", "WARN", "ERROR"):
        _handler.setLevel(lv)
        _logger_ = get_logger("Logger")
        _logger_.info("global logger set to %s" % lv)
        _LOG_LEVEL_ = lv
        for l in __cache_loggers.values():
            l.setLevel(lv)


def add_handler(handler):
    _handlers.append(handler)
    for l in __cache_loggers.values():
        l.addHandler(handler)


def remove_handler(handler):
    if handler in _handlers:
        _handlers.remove(handler)
    for l in __cache_loggers.values():
        l.removeHandler(handler)


def set_handler(handler):
    _handlers.clear()
    _handlers.append(handler)
    for l in __cache_loggers.values():
        for hdlr in l.handlers:
            l.removeHandler(hdlr)
        l.addHandler(handler)


def get_logger(tag="py-eureka-client"):
    if tag not in __cache_loggers:
        __cache_loggers[tag] = CachingLogger(tag, _LOG_LEVEL_)
        for hdlr in _handlers:
            __cache_loggers[tag].addHandler(hdlr)
    return __cache_loggers[tag]


def _log_msg_from_queue():
    while True:
        msg = _msg_cache.get()
        msg[0]._call_handlers(msg[1])


def _log_msg_in_backgrond():
    log_thread = Thread(target=_log_msg_from_queue, name="logging-thread")
    log_thread.daemon = True
    log_thread.start()


_log_msg_in_backgrond()
