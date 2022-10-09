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

version = "0.11.4"

"""
Status of instances
"""
INSTANCE_STATUS_UP: str = "UP"
INSTANCE_STATUS_DOWN: str = "DOWN"
INSTANCE_STATUS_STARTING: str = "STARTING"
INSTANCE_STATUS_OUT_OF_SERVICE: str = "OUT_OF_SERVICE"
INSTANCE_STATUS_UNKNOWN: str = "UNKNOWN"

"""
Action type of instances
"""
ACTION_TYPE_ADDED: str = "ADDED"
ACTION_TYPE_MODIFIED: str = "MODIFIED"
ACTION_TYPE_DELETED: str = "DELETED"

"""
This is for the DiscoveryClient, when this strategy is set, get_service_url will random choose one of the UP instance and return its url
This is the default strategy
"""
HA_STRATEGY_RANDOM: int = 1
"""
This is for the DiscoveryClient, when this strategy is set, get_service_url will always return one instance until it is down
"""
HA_STRATEGY_STICK: int = 2
"""
This is for the DiscoveryClient, when this strategy is set, get_service_url will always return a new instance if any other instances are up
"""
HA_STRATEGY_OTHER: int = 3

"""
The error types that will send back to on_error callback function
"""
ERROR_REGISTER: str = "EUREKA_ERROR_REGISTER"
ERROR_DISCOVER: str = "EUREKA_ERROR_DISCOVER"
ERROR_STATUS_UPDATE: str = "EUREKA_ERROR_STATUS_UPDATE"

"""
Default eureka server url.
"""
_DEFAULT_EUREKA_SERVER_URL = "http://127.0.0.1:8761/eureka/"
"""
Default instance field values
"""
_DEFAULT_INSTNACE_PORT = 9090
_DEFAULT_INSTNACE_SECURE_PORT = 9443
_RENEWAL_INTERVAL_IN_SECS = 30
_DURATION_IN_SECS = 90
_DEFAULT_DATA_CENTER_INFO = "MyOwn"
_DEFAULT_DATA_CENTER_INFO_CLASS = "com.netflix.appinfo.InstanceInfo$DefaultDataCenterInfo"
_AMAZON_DATA_CENTER_INFO_CLASS = "com.netflix.appinfo.AmazonInfo"
"""
Default configurations
"""
_DEFAULT_ENCODING = "utf-8"
_DEFAUTL_ZONE = "default"
"""
The timeout seconds that all http request to the eureka server
"""
_DEFAULT_TIME_OUT = 5
