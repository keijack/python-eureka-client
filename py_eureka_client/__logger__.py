# -*- coding: utf-8 -*-
import sys
import logging

_LOG_LEVEL_ = "INFO"


def set_level(level):
    global _LOG_LEVEL_
    lv = level.upper()
    if lv in ("DEBUG", "INFO", "WARN", "ERROR"):
        _logger_ = get_logger("Logger", "INFO")
        _logger_.info("global logger set to %s" % lv)
        _LOG_LEVEL_ = lv


def get_logger(tag="py_eureka_client", level=None):
    logger = logging.getLogger(tag)

    _formatter_ = logging.Formatter(fmt='[%(asctime)s]-[%(name)s]-[line:%(lineno)d] -%(levelname)-4s: %(message)s',
                                    datefmt='%Y-%m-%d %H:%M:%S')
    screen_handler = logging.StreamHandler(sys.stdout)
    screen_handler.setFormatter(_formatter_)
    if level is not None:
        logger.setLevel(level.upper())
        screen_handler.setLevel(level.upper())
    else:
        logger.setLevel(_LOG_LEVEL_)
        screen_handler.setLevel(_LOG_LEVEL_)

    logger.addHandler(screen_handler)
    return logger
