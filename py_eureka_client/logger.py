# -*- coding: utf-8 -*-

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

_msg_cache = queue.Queue(10000)


class CachingLogger(object):

    def __init__(self, name):
        self.name = name

    def _log(self, mth, msg, *args, **kwargs):
        _msg_cache.put({
            "name": self.name,
            "method": mth,
            "msg": msg,
            "args": args,
            "kwargs": kwargs,
        })

    def debug(self, msg, *args, **kwargs):
        self._log("debug", msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self._log("info", msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._log("warn", msg, *args, **kwargs)

    def warn(self, msg, *args, **kwargs):
        self._log("warn", msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self._log("error", msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        self.error(msg, *args, exc_info=sys.exc_info(), ** kwargs)


def set_level(level):
    lv = level.upper()
    if lv in ("DEBUG", "INFO", "WARN", "ERROR"):
        _handler.setLevel(lv)
        _logger_ = get_logger("Logger")
        _logger_.info("global logger set to %s" % lv)


def set_handler(handler):
    global _handler
    _handler = handler


def get_logger(tag="py-eureka-client"):
    if tag not in __cache_loggers:
        __cache_loggers[tag] = CachingLogger(tag)
    return __cache_loggers[tag]


def _get_real_logger(tag=""):
    # type (str, str) -> logging.Logger
    if tag in __loggers:
        return __loggers[tag]

    logger = logging.getLogger(tag)
    logger.addHandler(_handler)
    logger.setLevel(_handler.level)
    __loggers[tag] = logger
    return logger


def _log_():
    while(True):
        msg = _msg_cache.get()
        logger = _get_real_logger(msg["name"])
        mth = msg["method"]
        if mth == "debug":
            logger.debug(msg["msg"], *msg["args"], **msg["kwargs"])
        elif mth == "info":
            logger.info(msg["msg"], *msg["args"], **msg["kwargs"])
        elif mth == "warn":
            logger.warn(msg["msg"], *msg["args"], **msg["kwargs"])
        elif mth == "error":
            logger.error(msg["msg"], *msg["args"], **msg["kwargs"])


def _run_log_thread():
    log_thread = Thread(target=_log_, name="log_thread")
    log_thread.daemon = True
    log_thread.start()


_run_log_thread()
