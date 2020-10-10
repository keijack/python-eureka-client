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

import atexit
import json
import os
import re
import socket
import time
import random
import inspect
from copy import copy
import xml.etree.ElementTree as ElementTree
from threading import Timer
from threading import RLock
from threading import Thread
try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote


import py_eureka_client.http_client as http_client
from py_eureka_client.logger import get_logger
from py_eureka_client.__dns_txt_resolver import get_txt_dns_record
from py_eureka_client.__aws_info_loader import AmazonInfo


try:
    long(0)
except NameError:
    # python 3 does no longer support long method, use int instead
    long = int

_logger = get_logger("eureka_client")

"""
Status of instances
"""
INSTANCE_STATUS_UP = "UP"
INSTANCE_STATUS_DOWN = "DOWN"
INSTANCE_STATUS_STARTING = "STARTING"
INSTANCE_STATUS_OUT_OF_SERVICE = "OUT_OF_SERVICE"
INSTANCE_STATUS_UNKNOWN = "UNKNOWN"

"""
Action type of instances
"""
ACTION_TYPE_ADDED = "ADDED"
ACTION_TYPE_MODIFIED = "MODIFIED"
ACTION_TYPE_DELETED = "DELETED"

""" 
This is for the DiscoveryClient, when this strategy is set, get_service_url will random choose one of the UP instance and return its url
This is the default strategy
"""
HA_STRATEGY_RANDOM = 1
"""
This is for the DiscoveryClient, when this strategy is set, get_service_url will always return one instance until it is down
"""
HA_STRATEGY_STICK = 2
"""
This is for the DiscoveryClient, when this strategy is set, get_service_url will always return a new instance if any other instances are up
"""
HA_STRATEGY_OTHER = 3

"""
The timeout seconds that all http request to the eureka server
"""
_DEFAULT_TIME_OUT = 5
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

### =========================> Base Mehods <======================================== ###
### Beans ###


class Applications:

    def __init__(self,
                 apps__hashcode="",
                 versions__delta="",
                 applications=None):
        self.apps__hashcode = apps__hashcode
        self.versions__delta = versions__delta
        self.__applications = applications if applications is not None else []
        self.__application_name_dic = {}
        self.__app_lock = RLock()

    @property
    def appsHashcode(self):
        return self.apps__hashcode

    @property
    def applications(self):
        return self.__applications

    @property
    def versionsDelta(self):
        return self.versions__delta

    def add_application(self, application):
        with self.__app_lock:
            self.__applications.append(application)
            self.__application_name_dic[application.name] = application

    def get_application(self, app_name=""):
        with self.__app_lock:
            aname = app_name.upper()
            if app_name in self.__application_name_dic:
                return self.__application_name_dic[aname]
            else:
                return Application(name=aname)


class Application:

    def __init__(self,
                 name="",
                 instances=None):
        self.name = name
        if isinstance(instances, list):
            for ins in instances:
                self.add_instance(ins)
        self.__instances_dict = {}
        self.__inst_lock = RLock()

    @property
    def instances(self):
        with self.__inst_lock:
            return list(self.__instances_dict.values())

    @property
    def up_instances(self):
        with self.__inst_lock:
            return [item for item in self.__instances_dict.values() if item.status == INSTANCE_STATUS_UP]

    def get_instance(self, instance_id):
        with self.__inst_lock:
            if instance_id in self.__instances_dict:
                return self.__instances_dict[instance_id]
            else:
                return None

    def add_instance(self, instance):
        with self.__inst_lock:
            self.__instances_dict[instance.instanceId] = instance

    def update_instance(self, instance):
        with self.__inst_lock:
            _logger.debug("update instance %s" % instance.instanceId)
            self.__instances_dict[instance.instanceId] = instance

    def remove_instance(self, instance):
        with self.__inst_lock:
            if instance.instanceId in self.__instances_dict:
                del self.__instances_dict[instance.instanceId]

    def up_instances_in_zone(self, zone):
        with self.__inst_lock:
            _zone = zone if zone else _DEFAUTL_ZONE
            return [item for item in self.__instances_dict.values() if item.status == INSTANCE_STATUS_UP and item.zone == _zone]

    def up_instances_not_in_zone(self, zone):
        with self.__inst_lock:
            _zone = zone if zone else _DEFAUTL_ZONE
            return [item for item in self.__instances_dict.values() if item.status == INSTANCE_STATUS_UP and item.zone != _zone]


class LeaseInfo:

    def __init__(self,
                 renewalIntervalInSecs=_RENEWAL_INTERVAL_IN_SECS,
                 durationInSecs=_DURATION_IN_SECS,
                 registrationTimestamp=0,
                 lastRenewalTimestamp=0,
                 renewalTimestamp=0,
                 evictionTimestamp=0,
                 serviceUpTimestamp=0):
        self.renewalIntervalInSecs = renewalIntervalInSecs
        self.durationInSecs = durationInSecs
        self.registrationTimestamp = registrationTimestamp
        self.lastRenewalTimestamp = lastRenewalTimestamp
        self.renewalTimestamp = renewalTimestamp
        self.evictionTimestamp = evictionTimestamp
        self.serviceUpTimestamp = serviceUpTimestamp


class DataCenterInfo:

    def __init__(self,
                 name=_DEFAULT_DATA_CENTER_INFO,  # Netflix, Amazon, MyOwn
                 className=_DEFAULT_DATA_CENTER_INFO_CLASS,
                 metadata={}):
        self.name = name
        self.className = className
        self.metadata = metadata if metadata else {}


class PortWrapper:
    def __init__(self, port=0, enabled=False):
        self.port = port
        self.enabled = enabled


class Instance(object):

    def __init__(self,
                 instanceId="",
                 sid="",  # @deprecated
                 app="",
                 appGroupName="",
                 ipAddr="",
                 port=PortWrapper(port=_DEFAULT_INSTNACE_PORT, enabled=True),
                 securePort=PortWrapper(port=_DEFAULT_INSTNACE_SECURE_PORT, enabled=False),
                 homePageUrl="",
                 statusPageUrl="",
                 healthCheckUrl="",
                 secureHealthCheckUrl="",
                 vipAddress="",
                 secureVipAddress="",
                 countryId=1,
                 dataCenterInfo=DataCenterInfo(),
                 hostName="",
                 status="",  # UP, DOWN, STARTING, OUT_OF_SERVICE, UNKNOWN
                 overriddenstatus="",  # UP, DOWN, STARTING, OUT_OF_SERVICE, UNKNOWN
                 leaseInfo=LeaseInfo(),
                 isCoordinatingDiscoveryServer=False,
                 metadata=None,
                 lastUpdatedTimestamp=0,
                 lastDirtyTimestamp=0,
                 actionType=ACTION_TYPE_ADDED,  # ADDED, MODIFIED, DELETED
                 asgName=""):
        self.instanceId = instanceId
        self.sid = sid
        self.app = app
        self.appGroupName = appGroupName
        self.ipAddr = ipAddr
        self.port = port
        self.securePort = securePort
        self.homePageUrl = homePageUrl
        self.statusPageUrl = statusPageUrl
        self.healthCheckUrl = healthCheckUrl
        self.secureHealthCheckUrl = secureHealthCheckUrl
        self.vipAddress = vipAddress
        self.secureVipAddress = secureVipAddress
        self.countryId = countryId
        self.dataCenterInfo = dataCenterInfo
        self.hostName = hostName
        self.status = status
        self.overriddenstatus = overriddenstatus
        self.leaseInfo = leaseInfo
        self.isCoordinatingDiscoveryServer = isCoordinatingDiscoveryServer
        self.metadata = metadata if metadata is not None else {}
        self.lastUpdatedTimestamp = lastUpdatedTimestamp
        self.lastDirtyTimestamp = lastDirtyTimestamp
        self.actionType = actionType
        self.asgName = asgName

    @property
    def zone(self):
        if self.dataCenterInfo and self.dataCenterInfo.name == "Amazon" \
                and self.dataCenterInfo.metadata and "availability-zone" in self.dataCenterInfo.metadata:
            return self.dataCenterInfo.metadata["availability-zone"]
        if self.metadata and "zone" in self.metadata and self.metadata["zone"]:
            return self.metadata["zone"]
        else:
            return _DEFAUTL_ZONE


########################## Basic functions #################################
####### Registry functions #########
def register(eureka_server, instance):
    instance_dic = {
        'instanceId': instance.instanceId,
        'hostName': instance.hostName,
        'app': instance.app,
        'ipAddr': instance.ipAddr,
        'status': instance.status,
        'overriddenstatus': instance.overriddenstatus,
        'port': {
            '$': instance.port.port,
            '@enabled': str(instance.port.enabled).lower()
        },
        'securePort': {
            '$': instance.securePort.port,
            '@enabled': str(instance.securePort.enabled).lower()
        },
        'countryId': instance.countryId,
        'dataCenterInfo': {
            '@class': instance.dataCenterInfo.className,
            'name': instance.dataCenterInfo.name
        },
        'leaseInfo': {
            'renewalIntervalInSecs': instance.leaseInfo.renewalIntervalInSecs,
            'durationInSecs': instance.leaseInfo.durationInSecs,
            'registrationTimestamp': instance.leaseInfo.registrationTimestamp,
            'lastRenewalTimestamp': instance.leaseInfo.lastRenewalTimestamp,
            'evictionTimestamp': instance.leaseInfo.evictionTimestamp,
            'serviceUpTimestamp': instance.leaseInfo.serviceUpTimestamp
        },
        'metadata': instance.metadata,
        'homePageUrl': instance.homePageUrl,
        'statusPageUrl': instance.statusPageUrl,
        'healthCheckUrl': instance.healthCheckUrl,
        'secureHealthCheckUrl': instance.secureHealthCheckUrl,
        'vipAddress': instance.vipAddress,
        'secureVipAddress': instance.secureVipAddress,
        'lastUpdatedTimestamp': str(instance.lastUpdatedTimestamp),
        'lastDirtyTimestamp': str(instance.lastDirtyTimestamp),
        'isCoordinatingDiscoveryServer': str(instance.isCoordinatingDiscoveryServer).lower()
    }
    if instance.dataCenterInfo.metadata:
        instance_dic["dataCenterInfo"]["metadata"] = instance.dataCenterInfo.metadata
    _register(eureka_server, instance_dic)


def _register(eureka_server, instance_dic):
    req = http_client.Request(_format_url(eureka_server) + "apps/%s" % quote(instance_dic["app"]))
    req.add_header('Content-Type', 'application/json')
    req.get_method = lambda: "POST"
    http_client.load(req, json.dumps({"instance": instance_dic}).encode(_DEFAULT_ENCODING), timeout=_DEFAULT_TIME_OUT)


def cancel(eureka_server, app_name, instance_id):
    req = http_client.Request(_format_url(eureka_server) + "apps/%s/%s" % (quote(app_name), quote(instance_id)))
    req.get_method = lambda: "DELETE"
    http_client.load(req, timeout=_DEFAULT_TIME_OUT)


def status_update(eureka_server, app_name, instance_id, last_dirty_timestamp, status=INSTANCE_STATUS_UP, overriddenstatus=""):
    url = _format_url(eureka_server) + "apps/%s/%s/status?value=%s&lastDirtyTimestamp=%s" % \
        (quote(app_name), quote(instance_id), status, str(last_dirty_timestamp))
    if overriddenstatus != "":
        url += "&overriddenstatus=" + overriddenstatus

    req = http_client.Request(url)
    req.get_method = lambda: "PUT"
    http_client.load(req, timeout=_DEFAULT_TIME_OUT)


def delete_status_override(eureka_server, app_name, instance_id, last_dirty_timestamp):
    url = _format_url(eureka_server) + "apps/%s/%s/status?lastDirtyTimestamp=%s" % \
        (quote(app_name), quote(instance_id), str(last_dirty_timestamp))

    req = http_client.Request(url)
    req.get_method = lambda: "DELETE"
    http_client.load(req, timeout=_DEFAULT_TIME_OUT)


####### Discovory functions ########


def get_applications(eureka_server, regions=[]):
    return _get_applications_(_format_url(eureka_server) + "apps/", regions)


def _format_url(url):
    if url.endswith('/'):
        return url
    else:
        return url + "/"


def _get_applications_(url, regions=[]):
    _url = url
    if len(regions) > 0:
        _url = _url + ("&" if "?" in _url else "?") + "regions=" + (",".join(regions))

    txt = http_client.load(_url, timeout=_DEFAULT_TIME_OUT)
    return _build_applications(ElementTree.fromstring(txt.encode(_DEFAULT_ENCODING)))


def _build_applications(xml_node):
    if xml_node.tag != "applications":
        return None
    applications = Applications()
    for child_node in list(xml_node):
        if child_node.tag == "versions__delta" and child_node.text is not None:
            applications.versions__delta = child_node.text
        elif child_node.tag == "apps__hashcode" and child_node.text is not None:
            applications.apps__hashcode = child_node.text
        elif child_node.tag == "application":
            applications.add_application(_build_application(child_node))

    return applications


def _build_application(xml_node):
    if xml_node.tag != "application":
        return None
    application = Application()
    for child_node in xml_node:
        if child_node.tag == "name":
            application.name = child_node.text
        elif child_node.tag == "instance":
            application.add_instance(_build_instance(child_node))
    return application


def _build_instance(xml_node):
    if xml_node.tag != "instance":
        return None
    instance = Instance()
    for child_node in xml_node:
        if child_node.tag == "instanceId":
            instance.instanceId = child_node.text
        elif child_node.tag == "sid":
            instance.sid = child_node.text
        elif child_node.tag == "app":
            instance.app = child_node.text
        elif child_node.tag == "appGroupName":
            instance.appGroupName = child_node.text
        elif child_node.tag == "ipAddr":
            instance.ipAddr = child_node.text
        elif child_node.tag == "port":
            instance.port = _build_port(child_node)
        elif child_node.tag == "securePort":
            instance.securePort = _build_port(child_node)
        elif child_node.tag == "homePageUrl":
            instance.homePageUrl = child_node.text
        elif child_node.tag == "statusPageUrl":
            instance.statusPageUrl = child_node.text
        elif child_node.tag == "healthCheckUrl":
            instance.healthCheckUrl = child_node.text
        elif child_node.tag == "secureHealthCheckUrl":
            instance.secureHealthCheckUrl = child_node.text
        elif child_node.tag == "vipAddress":
            instance.vipAddress = child_node.text
        elif child_node.tag == "secureVipAddress":
            instance.secureVipAddress = child_node.text
        elif child_node.tag == "countryId":
            instance.countryId = int(child_node.text)
        elif child_node.tag == "dataCenterInfo":
            instance.dataCenterInfo = _build_data_center_info(child_node)
        elif child_node.tag == "hostName":
            instance.hostName = child_node.text
        elif child_node.tag == "status":
            instance.status = child_node.text
        elif child_node.tag == "overriddenstatus":
            instance.overriddenstatus = child_node.text
        elif child_node.tag == "leaseInfo":
            instance.leaseInfo = _build_lease_info(child_node)
        elif child_node.tag == "isCoordinatingDiscoveryServer":
            instance.isCoordinatingDiscoveryServer = (child_node.text == "true")
        elif child_node.tag == "metadata":
            instance.metadata = _build_metadata(child_node)
        elif child_node.tag == "lastUpdatedTimestamp":
            instance.lastUpdatedTimestamp = long(child_node.text)
        elif child_node.tag == "lastDirtyTimestamp":
            instance.lastDirtyTimestamp = long(child_node.text)
        elif child_node.tag == "actionType":
            instance.actionType = child_node.text
        elif child_node.tag == "asgName":
            instance.asgName = child_node.text

    return instance


def _build_data_center_info(xml_node):
    class_name = xml_node.attrib["class"]
    name = ""
    metadata = {}
    for child_node in xml_node:
        if child_node.tag == "name":
            name = child_node.text
        elif child_node.tag == "metadata":
            metadata = _build_metadata(child_node)

    return DataCenterInfo(name=name, className=class_name, metadata=metadata)


def _build_metadata(xml_node):
    metadata = {}
    for child_node in list(xml_node):
        metadata[child_node.tag] = child_node.text
    return metadata


def _build_lease_info(xml_node):
    leaseInfo = LeaseInfo()
    for child_node in list(xml_node):
        if child_node.tag == "renewalIntervalInSecs":
            leaseInfo.renewalIntervalInSecs = int(child_node.text)
        elif child_node.tag == "durationInSecs":
            leaseInfo.durationInSecs = int(child_node.text)
        elif child_node.tag == "registrationTimestamp":
            leaseInfo.registrationTimestamp = long(child_node.text)
        elif child_node.tag == "lastRenewalTimestamp":
            leaseInfo.lastRenewalTimestamp = long(child_node.text)
        elif child_node.tag == "renewalTimestamp":
            leaseInfo.renewalTimestamp = long(child_node.text)
        elif child_node.tag == "evictionTimestamp":
            leaseInfo.evictionTimestamp = long(child_node.text)
        elif child_node.tag == "serviceUpTimestamp":
            leaseInfo.serviceUpTimestamp = long(child_node.text)

    return leaseInfo


def _build_port(xml_node):
    port = PortWrapper()
    port.port = int(xml_node.text)
    port.enabled = (xml_node.attrib["enabled"] == "true")
    return port


def get_delta(eureka_server, regions=[]):
    return _get_applications_(_format_url(eureka_server) + "apps/delta", regions)


def get_vip(eureka_server, vip, regions=[]):
    return _get_applications_(_format_url(eureka_server) + "vips/" + vip, regions)


def get_secure_vip(eureka_server, svip, regions=[]):
    return _get_applications_(_format_url(eureka_server) + "svips/" + svip, regions)


def get_application(eureka_server, app_name):
    url = _format_url(eureka_server) + "apps/" + app_name
    txt = http_client.load(url, timeout=_DEFAULT_TIME_OUT)
    return _build_application(ElementTree.fromstring(txt))


def get_app_instance(eureka_server, app_name, instance_id):
    return _get_instance_(_format_url(eureka_server) + "apps/%s/%s" % (app_name, instance_id))


def get_instance(eureka_server, instance_id):
    return _get_instance_(_format_url(eureka_server) + "instances/" + instance_id)


def _get_instance_(url):
    txt = http_client.load(url, timeout=_DEFAULT_TIME_OUT)
    return _build_instance(ElementTree.fromstring(txt))


def _current_time_millis():
    return int(time.time() * 1000)


"""====================== Client ======================================="""


class EurekaServerConf(object):

    def __init__(self,
                 eureka_server=_DEFAULT_EUREKA_SERVER_URL,
                 eureka_domain="",
                 eureka_protocol="http",
                 eureka_basic_auth_user="",
                 eureka_basic_auth_password="",
                 eureka_context="eureka/v2",
                 eureka_availability_zones={},
                 region="",
                 zone=""):
        self.__servers = {}
        self.region = region
        self.__zone = zone
        self.__eureka_availability_zones = eureka_availability_zones
        _zone = zone if zone else _DEFAUTL_ZONE
        if eureka_domain:
            zone_urls = get_txt_dns_record("txt.%s.%s" % (region, eureka_domain))
            for zone_url in zone_urls:
                zone_name = zone_url.split(".")[0]
                eureka_urls = get_txt_dns_record("txt.%s" % zone_url)
                self.__servers[zone_name] = [self._format_url(eureka_url.strip(), eureka_protocol, eureka_basic_auth_user,
                                                              eureka_basic_auth_password, eureka_context) for eureka_url in eureka_urls]
        elif eureka_availability_zones:
            for zone_name, v in eureka_availability_zones.items():
                if isinstance(v, list):
                    eureka_urls = v
                else:
                    eureka_urls = str(v).split(",")
                self.__servers[zone_name] = [self._format_url(eureka_url.strip(), eureka_protocol, eureka_basic_auth_user,
                                                              eureka_basic_auth_password, eureka_context) for eureka_url in eureka_urls]
        else:
            self.__servers[_zone] = [self._format_url(eureka_url.strip(), eureka_protocol, eureka_basic_auth_user,
                                                      eureka_basic_auth_password, eureka_context) for eureka_url in eureka_server.split(",")]
        self.__servers_not_in_zone = copy(self.__servers)
        if _zone in self.__servers_not_in_zone:
            del self.__servers_not_in_zone[_zone]

    @property
    def zone(self):
        if self.__zone:
            return self.__zone
        elif self.__eureka_availability_zones:
            return self.__eureka_availability_zones.keys()[0]
        else:
            return _DEFAUTL_ZONE

    def _format_url(self, server_url="",
                    eureka_protocol="http",
                    eureka_basic_auth_user="",
                    eureka_basic_auth_password="",
                    eureka_context="eureka/v2"):
        url = server_url
        if url.endswith('/'):
            url = url[0: -1]
        if url.find("://") > 0:
            prtl, url = tuple(url.split("://"))
        else:
            prtl = eureka_protocol

        if url.find("@") > 0:
            basic_auth, url = tuple(url.split("@"))
            if basic_auth.find(":") > 0:
                user, password = tuple(basic_auth.split(":"))
            else:
                user = basic_auth
                password = ""
        else:
            user = quote(eureka_basic_auth_user)
            password = quote(eureka_basic_auth_password)

        basic_auth = ""
        if user:
            if password:
                basic_auth = user + ":" + password
            else:
                basic_auth = user
            basic_auth += "@"

        if url.find("/") > 0:
            ctx = ""
        else:
            ctx = eureka_context if eureka_context.startswith('/') else "/" + eureka_context

        return "%s://%s%s%s" % (prtl, basic_auth, url, ctx)

    @property
    def servers(self):
        return self.__servers

    @property
    def servers_in_zone(self):
        if self.zone in self.servers:
            return self.servers[self.zone]
        else:
            return []

    @property
    def servers_not_in_zone(self):
        return self.__servers_not_in_zone

class RegisterException(Exception):
    pass

class DiscoverException(Exception):
    pass

class EurekaClient(object):
    """
    Example:

    >>> client = EurekaClient(
            eureka_server="http://my_eureka_server_peer_1/eureka/v2,http://my_eureka_server_peer_2/eureka/v2", 
            app_name="python_module_1", 
            instance_port=9090)
    >>> client.start()
    >>> result = client.do_service("APP_NAME", "/context/path", return_type="json")

    EIPs support: 

    You can configure EIP using `eureka_availability_zones` and specify the `zone` of your instance. But please aware, that the client won't fill up the metadata atomatically, 
    You should put it to the `metadata` when creating the object.

    >>> client = EurekaClient(eureka_availability_zones={
                "us-east-1c": "http://ec2-552-627-568-165.compute-1.amazonaws.com:7001/eureka/v2/,http://ec2-368-101-182-134.compute-1.amazonaws.com:7001/eureka/v2/",
                "us-east-1d": "http://ec2-552-627-568-170.compute-1.amazonaws.com:7001/eureka/v2/",
                "us-east-1e": "http://ec2-500-179-285-592.compute-1.amazonaws.com:7001/eureka/v2/"}, 
                zone="us-east-1c",
                app_name="python_module_1",
                instance_port=9090,
                data_center_name="Amazon")

    EurekaClient supports DNS discovery feature.

    For instance, following is a DNS TXT record created in the DNS server that lists the set of available DNS names for a zone.

    >>> txt.us-east-1.mydomaintest.netflix.net="us-east-1c.mydomaintest.netflix.net" "us-east-1d.mydomaintest.netflix.net" "us-east-1e.mydomaintest.netflix.net"

    Then, you can define TXT records recursively for each zone similar to the following (if more than one hostname per zone, space delimit)

    >>> txt.us-east-1c.mydomaintest.netflix.net="ec2-552-627-568-165.compute-1.amazonaws.com" "ec2-368-101-182-134.compute-1.amazonaws.com"
    >>> txt.us-east-1d.mydomaintest.netflix.net="ec2-552-627-568-170.compute-1.amazonaws.com"
    >>> txt.us-east-1e.mydomaintest.netflix.net="ec2-500-179-285-592.compute-1.amazonaws.com"

    And then you can create the client like: 

    >>> client = EurekaClient(eureka_domain="mydomaintest.netflix.net",
                region="us-east-1",
                zone="us-east-1c",
                app_name="python_module_1", 
                instance_port=9090,
                data_center_name="Amazon")

    Eureka client also supports setting up the protocol, basic authentication and context path of your eureka server. 

    >>> client = EurekaClient(eureka_domain="mydomaintest.netflix.net",
                region="us-east-1",
                zone="us-east-1c",
                eureka_protocol="https",
                eureka_basic_auth_user="keijack",
                eureka_basic_auth_password="kjauthpass",
                eureka_context="/eureka/v2",
                app_name="python_module_1", 
                instance_port=9090,
                data_center_name="Amazon")

    or

    >>> client = EurekaClient(eureka_server="my_eureka_server_peer_1,my_eureka_server_peer_2",
                eureka_protocol="https",
                eureka_basic_auth_user="keijack",
                eureka_basic_auth_password="kjauthpass",
                eureka_context="/eureka/v2",
                app_name="python_module_1", 
                instance_port=9090)

    You can use `do_service`, `do_service_async`, `wall_nodes`, `wall_nodes_async` to call the remote services.

    >>> res = eureka_client.do_service("OTHER-SERVICE-NAME", "/service/context/path")

    >>> def success_callabck(data):
            ...

        def error_callback(error):
            ...

        client.do_service_async("OTHER-SERVICE-NAME", "/service/context/path", on_success=success_callabck, on_error=error_callback)

    >>> def walk_using_your_own_urllib(url):
            ...

        res = client.walk_nodes("OTHER-SERVICE-NAME", "/service/context/path", walker=walk_using_your_own_urllib)

    >>> client.walk_nodes("OTHER-SERVICE-NAME", "/service/context/path",
                          walker=walk_using_your_own_urllib,
                          on_success=success_callabck,
                          on_error=error_callback)


    Attributes:

    * eureka_server: The eureka server url, if you want have deploy a cluster to do the failover, use `,` to separate the urls.

    * eureka_domain: The domain name when using the DNS discovery.

    * region: The region when using DNS discovery.

    * zone: Which zone your instances belong to, default is `default`.

    * eureka_availability_zones: The zones' url configurations.

    * eureka_protocol: The protocol of the eureka server, if the url include this part, this protocol will not add to the url.

    * eureka_basic_auth_user: User name of the basic authentication of the eureka server, if the url include this part, this protocol will not add to the url.

    * eureka_basic_auth_password: Password of the basic authentication of the eureka server, if the url include this part, this protocol will not add to the url.

    * eureka_context: The context path of the eureka server, if the url include this part, this protocol will not add to the url, default is `/eureka`
        which meets the spring-boot eureka context but not the Netflix eureka server url.

    * prefer_same_zone: When set to True, will first find the eureka server in the same zone to register, and find the instances in the same zone to do
        the service. Or it will randomly choose the eureka server  to register and instances to do the services, default is `True`.

    * should_register: When set to False, will not register this instance to the eureka server, default is `True`.

    * should_discover: When set to False, will not pull registry from the eureka server, default is `True`.

    The following parameters all the properties of this instances, all this fields will be sent to the eureka server.

    * app_name: The application name of this instance.

    * instance_id: The id of this instance, if not specified, will generate one by app_name and instance_host/instance_ip and instance_port.

    * instance_host： The host of this instance. 

    * instance_ip: The ip of this instance. If instatnce_host and instance_ip are not specified, will try to find the ip via connection to the eureka server.

    * instance_port: The port of this instance. 

    * instance_unsecure_port_enabled: Set whether enable the instance's unsecure port, default is `True`.

    * instance_secure_port: The secure port of this instance. 

    * instance_secure_port_enabled: Set whether enable the instance's secure port, default is `False`.

    * data_center_name: Accept `Netflix`, `Amazon`, `MyOwn`, default is `MyOwn`

    * renewal_interval_in_secs: Will send heartbeat and pull registry in this time interval, defalut is 30 seconds

    * duration_in_secs: Sets the client specified setting for eviction (e.g. how long to wait without renewal event).

    * home_page_url: The home page url of this instance.

    * status_page_url: The status page url of this instance.

    * health_check_url: The health check url of this instance.

    * secure_health_check_url: The secure health check url of this instance.

    * vip_adr: The virtual ip address of this instance.

    * secure_vip_addr: The secure virtual ip address of this instance.

    * is_coordinating_discovery_server: Sets a flag if this instance is the same as the discovery server that is
        return the instances. This flag is used by the discovery clients to
        identity the discovery server which is coordinating/returning the
        information.

    * metadata: The metadata map of this instances.

    * remote_regions: Will also find the services that belongs to these regions.

    * ha_strategy: Specify the strategy how to choose a instance when there are more than one instanse of an App. 

    """

    def __init__(self,
                 eureka_server=_DEFAULT_EUREKA_SERVER_URL,
                 eureka_domain="",
                 region="",
                 zone="",
                 eureka_availability_zones={},
                 eureka_protocol="http",
                 eureka_basic_auth_user="",
                 eureka_basic_auth_password="",
                 eureka_context="/eureka",
                 prefer_same_zone=True,
                 should_register=True,
                 should_discover=True,
                 app_name="",
                 instance_id="",
                 instance_host="",
                 instance_ip="",
                 instance_port=_DEFAULT_INSTNACE_PORT,
                 instance_unsecure_port_enabled=True,
                 instance_secure_port=_DEFAULT_INSTNACE_SECURE_PORT,
                 instance_secure_port_enabled=False,
                 data_center_name=_DEFAULT_DATA_CENTER_INFO,  # Netflix, Amazon, MyOwn
                 renewal_interval_in_secs=_RENEWAL_INTERVAL_IN_SECS,
                 duration_in_secs=_DURATION_IN_SECS,
                 home_page_url="",
                 status_page_url="",
                 health_check_url="",
                 secure_health_check_url="",
                 vip_adr="",
                 secure_vip_addr="",
                 is_coordinating_discovery_server=False,
                 metadata={},
                 remote_regions=[],
                 ha_strategy=HA_STRATEGY_RANDOM):
        assert app_name is not None and app_name != "" if should_register else True, "application name must be specified."
        assert instance_port > 0 if should_register else True, "port is unvalid"
        assert isinstance(metadata, dict), "metadata must be dict"
        assert ha_strategy in [HA_STRATEGY_RANDOM, HA_STRATEGY_STICK,
                               HA_STRATEGY_OTHER] if should_discover else True, "do not support strategy %d " % ha_strategy

        self.__net_lock = RLock()
        self.__eureka_server_conf = EurekaServerConf(
            eureka_server=eureka_server,
            eureka_domain=eureka_domain,
            eureka_protocol=eureka_protocol,
            eureka_basic_auth_user=eureka_basic_auth_user,
            eureka_basic_auth_password=eureka_basic_auth_password,
            eureka_context=eureka_context,
            eureka_availability_zones=eureka_availability_zones,
            region=region,
            zone=zone
        )
        self.__cache_eureka_url = {}
        self.__should_register = should_register
        self.__should_discover = should_discover
        self.__prefer_same_zone = prefer_same_zone
        self.__alive = False
        self.__heartbeat_timer = Timer(renewal_interval_in_secs, self.__heartbeat)
        self.__heartbeat_timer.daemon = True

        def try_to_get_client_ip(url):
            if instance_host == "" and instance_ip == "":
                self.__instance_host = self.__instance_ip = EurekaClient.__get_instance_ip(url)
            elif instance_host != "" and instance_ip == "":
                self.__instance_host = instance_host
                if EurekaClient.__is_ip(instance_host):
                    self.__instance_ip = instance_host
                else:
                    self.__instance_ip = EurekaClient.__get_instance_ip(url)
            else:
                self.__instance_host = instance_ip
                self.__instance_ip = instance_ip

        # For Registery
        if should_register:
            self.__connect_to_eureka_server(try_to_get_client_ip)

        mdata = {
            'management.port': str(instance_port)
        }
        if zone:
            mdata["zone"] = zone
        mdata.update(metadata)
        self.__instance = {
            'instanceId': instance_id if instance_id != "" else "%s:%s:%d" % (self.__instance_host, app_name.lower(), instance_port),
            'hostName': self.__instance_host,
            'app': app_name.upper(),
            'ipAddr': self.__instance_ip,
            'port': {
                '$': instance_port,
                '@enabled': str(instance_unsecure_port_enabled).lower()
            },
            'securePort': {
                '$': instance_secure_port,
                '@enabled': str(instance_secure_port_enabled).lower()
            },
            'countryId': 1,
            'dataCenterInfo': {
                '@class': _AMAZON_DATA_CENTER_INFO_CLASS if data_center_name == "Amazon" else _DEFAULT_DATA_CENTER_INFO_CLASS,
                'name': data_center_name
            },
            'leaseInfo': {
                'renewalIntervalInSecs': renewal_interval_in_secs,
                'durationInSecs': duration_in_secs,
                'registrationTimestamp': 0,
                'lastRenewalTimestamp': 0,
                'evictionTimestamp': 0,
                'serviceUpTimestamp': 0
            },
            'metadata': mdata,
            'homePageUrl': EurekaClient.__format_url(home_page_url, self.__instance_host, instance_port),
            'statusPageUrl': EurekaClient.__format_url(status_page_url, self.__instance_host, instance_port, "info"),
            'healthCheckUrl': EurekaClient.__format_url(health_check_url, self.__instance_host, instance_port, "health"),
            'secureHealthCheckUrl': secure_health_check_url,
            'vipAddress': vip_adr if vip_adr != "" else app_name.lower(),
            'secureVipAddress': secure_vip_addr if secure_vip_addr != "" else app_name.lower(),
            'isCoordinatingDiscoveryServer': str(is_coordinating_discovery_server).lower()
        }
        if data_center_name == "Amazon":
            self.__instance["dataCenterInfo"]["metadata"] = self.__load_ec2_metadata_dict()

        # For discovery
        self.__remote_regions = remote_regions if remote_regions is not None else []
        self.__applications = None
        self.__delta = None
        self.__ha_strategy = ha_strategy
        self.__ha_cache = {}

        self.__application_mth_lock = RLock()

    def __load_ec2_metadata_dict(self):
        # instance metadata
        amazon_info = AmazonInfo()
        mac = amazon_info.get_ec2_metadata('mac')
        if mac:
            vpc_id = amazon_info.get_ec2_metadata('network/interfaces/macs/%s/vpc-id' % mac)
        else:
            vpc_id = ""
        metadata = {
            'instance-id': amazon_info.get_ec2_metadata('instance-id'),
            'ami-id': amazon_info.get_ec2_metadata('ami-id'),
            'instance-type': amazon_info.get_ec2_metadata('instance-type'),
            'local-ipv4': amazon_info.get_ec2_metadata('local-ipv4'),
            'local-hostname': amazon_info.get_ec2_metadata('local-hostname'),
            'availability-zone': amazon_info.get_ec2_metadata('placement/availability-zone'),
            'public-hostname': amazon_info.get_ec2_metadata('public-hostname'),
            'public-ipv4': amazon_info.get_ec2_metadata('public-ipv4'),
            'mac': mac,
            'vpcId': vpc_id
        }
        # accountId
        doc = amazon_info.get_instance_identity_document()
        if doc and "accountId" in doc:
            metadata["accountId"] = doc["accountId"]
        return metadata

    @property
    def should_register(self):
        return self.__should_register

    @property
    def should_discover(self):
        return self.__should_discover

    @property
    def zone(self):
        return self.__eureka_server_conf.zone

    @property
    def applications(self):
        if not self.should_discover:
            raise DiscoverException("should_discover set to False, no registry is pulled, cannot find any applications.")
        with self.__application_mth_lock:
            if self.__applications is None:
                self.__pull_full_registry()
            return self.__applications

    def __try_eureka_server_in_cache(self, fun):
        for z, url in self.__cache_eureka_url.items():
            _logger.debug("try to do %s in zone[%s] using cached url %s. " % (fun.__name__, z, url))
            fun(url)

    def __try_eureka_server_in_zone(self, fun):
        self.__try_eureka_servers_in_list(fun, self.__eureka_server_conf.servers_in_zone, self.zone)

    def __try_eureka_server_not_in_zone(self, fun):
        for zone, urls in self.__eureka_server_conf.servers_not_in_zone.items():
            try:
                self.__try_eureka_servers_in_list(fun, urls, zone)
            except (http_client.HTTPError, http_client.URLError):
                _logger.exception("error!")
            else:
                return
        raise http_client.URLError("All eureka servers in all zone are down!")

    def __try_eureka_server_regardless_zones(self, fun):
        for zone, urls in self.__eureka_server_conf.servers.items():
            try:
                self.__try_eureka_servers_in_list(fun, urls, zone)
            except (http_client.HTTPError, http_client.URLError):
                _logger.exception("error!")
            else:
                return
        raise http_client.URLError("All eureka servers in all zone are down!")

    def __try_all_eureka_servers(self, fun):
        if self.__prefer_same_zone:
            try:
                self.__try_eureka_server_in_zone(fun)
            except (http_client.HTTPError, http_client.URLError):
                self.__try_eureka_server_not_in_zone(fun)
        else:
            self.__try_eureka_server_regardless_zones(fun)

    def __try_eureka_servers_in_list(self, fun, eureka_servers=[], zone=_DEFAUTL_ZONE):
        with self.__net_lock:
            ok = False
            _zone = zone if zone else _DEFAUTL_ZONE
            for url in eureka_servers:
                url = url.strip()
                try:
                    _logger.debug("try to do %s in zone[%s] using url %s. " % (fun.__name__, _zone, url))
                    fun(url)
                except (http_client.HTTPError, http_client.URLError):
                    _logger.exception("Eureka server [%s] is down, use next url to try." % url)
                else:
                    ok = True
                    self.__cache_eureka_url[_zone] = url
                    break

            if not ok:
                if _zone in self.__cache_eureka_url:
                    del self.__cache_eureka_url[_zone]
                raise http_client.URLError("All eureka servers in zone[%s] are down!" % _zone)

    def __connect_to_eureka_server(self, fun):
        if self.__cache_eureka_url:
            try:
                self.__try_eureka_server_in_cache(fun)
            except (http_client.HTTPError, http_client.URLError):
                self.__try_all_eureka_servers(fun)
        else:
            self.__try_all_eureka_servers(fun)

    @staticmethod
    def __format_url(url, host, port, defalut_ctx=""):
        if url != "":
            if url.startswith('http'):
                _url = url
            elif url.startswith('/'):
                _url = 'http://%s:%d%s' % (host, port, url)
            else:
                _url = 'http://%s:%d/%s' % (host, port, url)
        else:
            _url = 'http://%s:%d/%s' % (host, port, defalut_ctx)
        return _url

    @staticmethod
    def __is_ip(ip_str):
        return re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip_str)

    @staticmethod
    def __get_instance_ip(eureka_server):
        url_obj = http_client.parse_url(eureka_server)
        target_ip = url_obj["host"]
        target_port = url_obj["port"]
        if target_port is None:
            if url_obj["schema"] == "http":
                target_port = 80
            else:
                target_port = 443

        if url_obj["ipv6"] is not None:
            target_ip = url_obj["ipv6"]
            socket_family = socket.AF_INET6
        else:
            socket_family = socket.AF_INET

        s = socket.socket(socket_family, socket.SOCK_DGRAM)
        s.connect((target_ip, target_port))
        ip = s.getsockname()[0]
        s.close()
        return ip

    def register(self, status=INSTANCE_STATUS_UP, overriddenstatus=INSTANCE_STATUS_UNKNOWN):
        self.__instance["status"] = status
        self.__instance["overriddenstatus"] = overriddenstatus
        self.__instance["lastUpdatedTimestamp"] = str(_current_time_millis())
        self.__instance["lastDirtyTimestamp"] = str(_current_time_millis())
        try:
            self.__connect_to_eureka_server(lambda url: _register(url, self.__instance))
        except:
            self.__alive = False
            _logger.exception("register error!")
        else:
            _logger.debug("register successfully!")
            self.__alive = True

    def cancel(self):
        try:
            self.__connect_to_eureka_server(lambda url: cancel(url, self.__instance["app"], self.__instance["instanceId"]))
        except:
            _logger.exception("error!")
        else:
            self.__alive = False

    def send_heartbeat(self, overridden_status=""):
        if not self.__alive:
            self.register()
            return
        try:
            self.__connect_to_eureka_server(lambda url: status_update(url, self.__instance["app"],
                                                                      self.__instance["instanceId"], self.__instance["lastDirtyTimestamp"],
                                                                      status=self.__instance["status"], overriddenstatus=overridden_status))
        except:
            _logger.exception("Error!")
            _logger.info("Cannot send heartbeat to server, try to register")
            self.register()

    def status_update(self, new_status):
        self.__instance["status"] = new_status
        try:
            self.__connect_to_eureka_server(lambda url: status_update(url, self.__instance["app"], self.__instance["instanceId"],
                                                                      self.__instance["lastDirtyTimestamp"], new_status))
        except:
            _logger.exception("error!")

    def delete_status_override(self):
        self.__connect_to_eureka_server(lambda url: delete_status_override(
            url, self.__instance["app"], self.__instance["instanceId"], self.__instance["lastDirtyTimestamp"]))

    def __start_register(self):
        _logger.debug("start to registry client...")
        self.register()

    def __stop_registery(self):
        if self.__alive:
            self.register(status=INSTANCE_STATUS_DOWN)
            self.cancel()

    def __heartbeat(self):
        while True:
            if self.__should_register:
                _logger.debug("sending heartbeat to eureka server ")
                self.send_heartbeat()
            if self.__should_discover:
                _logger.debug("loading services from  eureka server")
                self.__fetch_delta()
            time.sleep(self.__instance["leaseInfo"]["renewalIntervalInSecs"])

    def __pull_full_registry(self):
        def do_pull(url):  # the actual function body
            self.__applications = get_applications(url, self.__remote_regions)
            self.__delta = self.__applications
        try:
            self.__connect_to_eureka_server(do_pull)
        except:
            _logger.exception("pull full registry from eureka server error!")

    def __fetch_delta(self):
        def do_fetch(url):
            if self.__applications is None or len(self.__applications.applications) == 0:
                self.__pull_full_registry()
                return
            delta = get_delta(url, self.__remote_regions)
            _logger.debug("delta got: v.%s::%s" % (delta.versionsDelta, delta.appsHashcode))
            if self.__delta is not None \
                    and delta.versionsDelta == self.__delta.versionsDelta \
                    and delta.appsHashcode == self.__delta.appsHashcode:
                return
            self.__merge_delta(delta)
            self.__delta = delta
            if not self.__is_hash_match():
                self.__pull_full_registry()
        try:
            self.__connect_to_eureka_server(do_fetch)
        except:
            _logger.exception("fetch delta from eureka server error!")

    def __is_hash_match(self):
        app_hash = self.__get_applications_hash()
        _logger.debug("check hash, local[%s], remote[%s]" % (app_hash, self.__delta.appsHashcode))
        return app_hash == self.__delta.appsHashcode

    def __merge_delta(self, delta):
        _logger.debug("merge delta...length of application got from delta::%d" % len(delta.applications))
        for application in delta.applications:
            for instance in application.instances:
                _logger.debug("instance [%s] has %s" % (instance.instanceId, instance.actionType))
                if instance.actionType in (ACTION_TYPE_ADDED, ACTION_TYPE_MODIFIED):
                    existingApp = self.applications.get_application(application.name)
                    if existingApp is None:
                        self.applications.add_application(application)
                    else:
                        existingApp.update_instance(instance)
                elif instance.actionType == ACTION_TYPE_DELETED:
                    existingApp = self.applications.get_application(application.name)
                    if existingApp is None:
                        self.applications.add_application(application)
                    existingApp.remove_instance(instance)

    def __get_applications_hash(self):
        app_hash = ""
        app_status_count = {}
        for application in self.__applications.applications:
            for instance in application.instances:
                if instance.status not in app_status_count:
                    app_status_count[instance.status.upper()] = 0
                app_status_count[instance.status.upper()] = app_status_count[instance.status.upper()] + 1

        sorted_app_status_count = sorted(app_status_count.items(), key=lambda item: item[0])
        for item in sorted_app_status_count:
            app_hash = app_hash + "%s_%d_" % (item[0], item[1])
        return app_hash

    def walk_nodes_async(self, app_name="", service="", prefer_ip=False, prefer_https=False, walker=None, on_success=None, on_error=None):
        def async_thread_target():
            try:
                res = self.walk_nodes(app_name=app_name, service=service, prefer_ip=prefer_ip, prefer_https=prefer_https, walker=walker)
                if on_success is not None and (inspect.isfunction(on_success) or inspect.ismethod(on_success)):
                    on_success(res)
            except http_client.HTTPError as e:
                if on_error is not None and (inspect.isfunction(on_error) or inspect.ismethod(on_error)):
                    on_error(e)

        async_thread = Thread(target=async_thread_target)
        async_thread.daemon = True
        async_thread.start()

    def walk_nodes(self, app_name="", service="", prefer_ip=False, prefer_https=False, walker=None):
        assert app_name is not None and app_name != "", "application_name should not be null"
        assert inspect.isfunction(walker) or inspect.ismethod(walker), "walker must be a method or function"
        error_nodes = []
        app_name = app_name.upper()
        node = self.__get_available_service(app_name)

        while node is not None:
            try:
                url = self.__generate_service_url(node, prefer_ip, prefer_https)
                if service.startswith("/"):
                    url = url + service[1:]
                else:
                    url = url + service
                _logger.debug("do service with url::" + url)
                return walker(url)
            except (http_client.HTTPError, http_client.URLError):
                _logger.warn("do service %s in node [%s] error, use next node." % (service, node.instanceId))
                error_nodes.append(node.instanceId)
                node = self.__get_available_service(app_name, error_nodes)

        raise http_client.URLError("Try all up instances in registry, but all fail")

    def do_service_async(self, app_name="", service="", return_type="string",
                         prefer_ip=False, prefer_https=False,
                         on_success=None, on_error=None,
                         method="GET", headers=None,
                         data=None, timeout=_DEFAULT_TIME_OUT,
                         cafile=None, capath=None, cadefault=False, context=None):
        def async_thread_target():
            try:
                res = self.do_service(app_name=app_name,
                                      service=service, return_type=return_type,
                                      prefer_ip=prefer_ip, prefer_https=prefer_https,
                                      method=method, headers=headers,
                                      data=data, timeout=timeout,
                                      cafile=cafile, capath=capath,
                                      cadefault=cadefault, context=context)
                if on_success is not None and (inspect.isfunction(on_success) or inspect.ismethod(on_success)):
                    on_success(res)
            except http_client.HTTPError as e:
                if on_error is not None and (inspect.isfunction(on_error) or inspect.ismethod(on_error)):
                    on_error(e)

        async_thread = Thread(target=async_thread_target)
        async_thread.daemon = True
        async_thread.start()

    def do_service(self, app_name="", service="", return_type="string",
                   prefer_ip=False, prefer_https=False,
                   method="GET", headers=None,
                   data=None, timeout=_DEFAULT_TIME_OUT,
                   cafile=None, capath=None, cadefault=False, context=None):
        def walk_using_urllib(url):
            req = http_client.Request(url)
            req.get_method = lambda: method
            heads = headers if headers is not None else {}
            for k, v in heads.items():
                req.add_header(k, v)

            res_txt = http_client.load(req, data=data, timeout=timeout, cafile=cafile, capath=capath, cadefault=cadefault, context=context)
            if return_type.lower() in ("json", "dict", "dictionary"):
                return json.loads(res_txt)
            else:
                return res_txt
        return self.walk_nodes(app_name, service, prefer_ip, prefer_https, walk_using_urllib)

    def __get_service_not_in_ignore_list(self, instances, ignores):
        ign = ignores if ignores else []
        return [item for item in instances if item.instanceId not in ign]

    def __get_available_service(self, application_name, ignore_instance_ids=None):
        app = self.applications.get_application(application_name)
        if app is None:
            return None
        up_instances = []
        if self.__prefer_same_zone:
            ups_same_zone = app.up_instances_in_zone(self.zone)
            up_instances = self.__get_service_not_in_ignore_list(ups_same_zone, ignore_instance_ids)
            if not up_instances:
                ups_not_same_zone = app.up_instances_not_in_zone(self.zone)
                _logger.debug("app[%s]'s up instances not in same zone are all down, using the one that's not in the same zone: %s" %
                              (application_name, str([ins.instanceId for ins in ups_not_same_zone])))
                up_instances = self.__get_service_not_in_ignore_list(ups_not_same_zone, ignore_instance_ids)
        else:
            up_instances = self.__get_service_not_in_ignore_list(app.up_instances, ignore_instance_ids)

        if len(up_instances) == 0:
            # no up instances
            return None
        elif len(up_instances) == 1:
            # only one available instance, then doesn't matter which strategy is.
            instance = up_instances[0]
            self.__ha_cache[application_name] = instance.instanceId
            return instance

        def random_one(instances):
            if len(instances) == 1:
                idx = 0
            else:
                idx = random.randint(0, len(instances) - 1)
            selected_instance = instances[idx]
            self.__ha_cache[application_name] = selected_instance.instanceId
            return selected_instance

        if self.__ha_strategy == HA_STRATEGY_RANDOM:
            return random_one(up_instances)
        elif self.__ha_strategy == HA_STRATEGY_STICK:
            if application_name in self.__ha_cache:
                cache_id = self.__ha_cache[application_name]
                cahce_instance = app.get_instance(cache_id)
                if cahce_instance is not None and cahce_instance.status == INSTANCE_STATUS_UP:
                    return cahce_instance
                else:
                    return random_one(up_instances)
            else:
                return random_one(up_instances)
        elif self.__ha_strategy == HA_STRATEGY_OTHER:
            if application_name in self.__ha_cache:
                cache_id = self.__ha_cache[application_name]
                other_instances = []
                for up_instance in up_instances:
                    if up_instance.instanceId != cache_id:
                        other_instances.append(up_instance)
                return random_one(other_instances)
            else:
                return random_one(up_instances)
        else:
            return None

    def __generate_service_url(self, instance, prefer_ip, prefer_https):
        if instance is None:
            return None
        schema = "http"
        port = 0
        if instance.port.port and not instance.securePort.enabled:
            schema = "http"
            port = instance.port.port
        elif not instance.port.port and instance.securePort.enabled:
            schema = "https"
            port = instance.securePort.port
        elif instance.port.port and instance.securePort.enabled:
            if prefer_https:
                schema = "https"
                port = instance.securePort.port
            else:
                schema = "http"
                port = instance.port.port
        else:
            assert False, "generate_service_url error: No port is available"

        host = instance.ipAddr if prefer_ip else instance.hostName

        return "%s://%s:%d/" % (schema, host, port)

    def __start_discover(self):
        self.__pull_full_registry()

    def start(self):
        if self.should_register:
            self.__start_register()
        if self.should_discover:
            self.__start_discover()
        self.__heartbeat_timer.start()

    def stop(self):
        if self.__heartbeat_timer.isAlive():
            self.__heartbeat_timer.cancel()
        if self.__should_register:
            self.__stop_registery()


__cache_key = "default"
__cache_clients = {}
__cache_clients_lock = RLock()


def init(eureka_server=_DEFAULT_EUREKA_SERVER_URL,
         eureka_domain="",
         region="",
         zone="",
         eureka_availability_zones={},
         eureka_protocol="http",
         eureka_basic_auth_user="",
         eureka_basic_auth_password="",
         eureka_context="eureka/v2",
         should_register=True,
         should_discover=True,
         app_name="",
         instance_id="",
         instance_host="",
         instance_ip="",
         instance_port=_DEFAULT_INSTNACE_PORT,
         instance_unsecure_port_enabled=True,
         instance_secure_port=_DEFAULT_INSTNACE_SECURE_PORT,
         instance_secure_port_enabled=False,
         data_center_name=_DEFAULT_DATA_CENTER_INFO,  # Netflix, Amazon, MyOwn
         renewal_interval_in_secs=_RENEWAL_INTERVAL_IN_SECS,
         duration_in_secs=_DURATION_IN_SECS,
         home_page_url="",
         status_page_url="",
         health_check_url="",
         secure_health_check_url="",
         vip_adr="",
         secure_vip_addr="",
         is_coordinating_discovery_server=False,
         metadata={},
         remote_regions=[],
         ha_strategy=HA_STRATEGY_RANDOM):
    """
    Initialize an EurekaClient object and put it to cache, you can use a set of functions to do the service.

    Unlike using EurekaClient class that you need to start and stop the client object by yourself, this method 
    will start the client automatically after the object created and stop it when the programe exist.

    read EurekaClient for more information for the parameters details.
    """
    with __cache_clients_lock:
        if __cache_key in __cache_clients:
            _logger.warn("A client is already running, try to stop it and start the new one!")
            __cache_clients[__cache_key].stop()
            del __cache_clients[__cache_key]
        client = EurekaClient(eureka_server=eureka_server,
                              eureka_domain=eureka_domain,
                              region=region,
                              zone=zone,
                              eureka_availability_zones=eureka_availability_zones,
                              eureka_protocol=eureka_protocol,
                              eureka_basic_auth_user=eureka_basic_auth_user,
                              eureka_basic_auth_password=eureka_basic_auth_password,
                              eureka_context=eureka_context,
                              should_register=should_register,
                              should_discover=should_discover,
                              app_name=app_name,
                              instance_id=instance_id,
                              instance_host=instance_host,
                              instance_ip=instance_ip,
                              instance_port=instance_port,
                              instance_unsecure_port_enabled=instance_unsecure_port_enabled,
                              instance_secure_port=instance_secure_port,
                              instance_secure_port_enabled=instance_secure_port_enabled,
                              data_center_name=data_center_name,
                              renewal_interval_in_secs=renewal_interval_in_secs,
                              duration_in_secs=duration_in_secs,
                              home_page_url=home_page_url,
                              status_page_url=status_page_url,
                              health_check_url=health_check_url,
                              secure_health_check_url=secure_health_check_url,
                              vip_adr=vip_adr,
                              secure_vip_addr=secure_vip_addr,
                              is_coordinating_discovery_server=is_coordinating_discovery_server,
                              metadata=metadata,
                              remote_regions=remote_regions,
                              ha_strategy=ha_strategy)
        __cache_clients[__cache_key] = client
        client.start()
        return client


def init_registry_client(eureka_server=_DEFAULT_EUREKA_SERVER_URL,
                         app_name="",
                         instance_id="",
                         instance_host="",
                         instance_ip="",
                         instance_port=_DEFAULT_INSTNACE_PORT,
                         instance_unsecure_port_enabled=True,
                         instance_secure_port=_DEFAULT_INSTNACE_SECURE_PORT,
                         instance_secure_port_enabled=False,
                         data_center_name=_DEFAULT_DATA_CENTER_INFO,  # Netflix, Amazon, MyOwn
                         renewal_interval_in_secs=_RENEWAL_INTERVAL_IN_SECS,
                         duration_in_secs=_DURATION_IN_SECS,
                         home_page_url="",
                         status_page_url="",
                         health_check_url="",
                         secure_health_check_url="",
                         vip_adr="",
                         secure_vip_addr="",
                         is_coordinating_discovery_server=False,
                         metadata={}):
    """
    Deprecated， use `init` instead
    """
    return init(eureka_server=eureka_server,
                should_discover=False,
                app_name=app_name,
                instance_id=instance_id,
                instance_host=instance_host,
                instance_ip=instance_ip,
                instance_port=instance_port,
                instance_unsecure_port_enabled=instance_unsecure_port_enabled,
                instance_secure_port=instance_secure_port,
                instance_secure_port_enabled=instance_secure_port_enabled,
                data_center_name=data_center_name,
                renewal_interval_in_secs=renewal_interval_in_secs,
                duration_in_secs=duration_in_secs,
                home_page_url=home_page_url,
                status_page_url=status_page_url,
                health_check_url=health_check_url,
                secure_health_check_url=secure_health_check_url,
                vip_adr=vip_adr,
                secure_vip_addr=secure_vip_addr,
                is_coordinating_discovery_server=is_coordinating_discovery_server,
                metadata=metadata)


def init_discovery_client(eureka_server=_DEFAULT_EUREKA_SERVER_URL,
                          regions=[],  # Deprecated
                          renewal_interval_in_secs=_RENEWAL_INTERVAL_IN_SECS,
                          ha_strategy=HA_STRATEGY_RANDOM):
    """
    Deprecated， use `init` instead
    """
    return init(eureka_server=eureka_server,
                should_register=False,
                remote_regions=regions,
                renewal_interval_in_secs=renewal_interval_in_secs,
                ha_strategy=ha_strategy)


def get_client():
    # type () -> EurekaClient
    with __cache_clients_lock:
        if __cache_key in __cache_clients:
            return __cache_clients[__cache_key]
        else:
            return None


def get_registry_client():
    cli = get_client()
    if cli.should_register:
        return cli


def get_discovery_client():
    cli = get_client()
    if cli.should_discover:
        return cli


def walk_nodes_async(app_name="", service="", prefer_ip=False, prefer_https=False, walker=None, on_success=None, on_error=None):
    cli = get_discovery_client()
    if cli is None:
        raise Exception("Discovery Client has not initialized. ")
    cli.walk_nodes_async(app_name=app_name, service=service,
                         prefer_ip=prefer_ip, prefer_https=prefer_https,
                         walker=walker, on_success=on_success, on_error=on_error)


def walk_nodes(app_name="", service="", prefer_ip=False, prefer_https=False, walker=None):
    cli = get_discovery_client()
    if cli is None:
        raise Exception("Discovery Client has not initialized. ")
    return cli.walk_nodes(app_name=app_name, service=service,
                          prefer_ip=prefer_ip, prefer_https=prefer_https, walker=walker)


def do_service_async(app_name="", service="", return_type="string",
                     prefer_ip=False, prefer_https=False,
                     on_success=None, on_error=None,
                     method="GET", headers=None,
                     data=None, timeout=_DEFAULT_TIME_OUT,
                     cafile=None, capath=None, cadefault=False, context=None):
    cli = get_discovery_client()
    if cli is None:
        raise Exception("Discovery Client has not initialized. ")
    cli.do_service_async(app_name=app_name, service=service, return_type=return_type,
                         prefer_ip=prefer_ip, prefer_https=prefer_https,
                         on_success=on_success, on_error=on_error,
                         method=method, headers=headers,
                         data=data, timeout=timeout,
                         cafile=cafile, capath=capath,
                         cadefault=cadefault, context=context)


def do_service(app_name="", service="", return_type="string",
               prefer_ip=False, prefer_https=False,
               method="GET", headers=None,
               data=None, timeout=_DEFAULT_TIME_OUT,
               cafile=None, capath=None, cadefault=False, context=None):
    cli = get_discovery_client()
    if cli is None:
        raise Exception("Discovery Client has not initialized. ")
    return cli.do_service(app_name=app_name, service=service, return_type=return_type,
                          prefer_ip=prefer_ip, prefer_https=prefer_https,
                          method=method, headers=headers,
                          data=data, timeout=timeout,
                          cafile=cafile, capath=capath,
                          cadefault=cadefault, context=context)


def stop():
    client = get_client()
    if client is not None:
        client.stop()


@atexit.register
def _cleanup_before_exist():
    if len(__cache_clients) > 0:
        _logger.debug("cleaning up clients")
        for k, cli in __cache_clients.items():
            _logger.debug("try to stop cache client [%s] this will also unregister this client from the eureka server" % k)
            cli.stop()
