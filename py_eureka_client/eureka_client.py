# -*- coding: utf-8 -*-

import atexit
import json
import os
import re
import socket
import time
import random
import inspect
import xml.etree.ElementTree as ElementTree
from threading import Timer
from threading import RLock
from threading import Thread
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

from py_eureka_client.__logger__ import get_logger
import py_eureka_client.http_client as http_client

try:
    long(0)
except NameError:
    # python 3 does no longer support long method, use int instead
    long = int

_logger = get_logger("EurekaClient")

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
"""
Default encoding
"""
_DEFAULT_ENCODING = "utf-8"

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

    def get_application(self, app_name):
        with self.__app_lock:
            if app_name in self.__application_name_dic:
                return self.__application_name_dic[app_name]
            else:
                return Application(name=app_name)


class Application:

    def __init__(self,
                 name="",
                 instances=None):
        self.name = name
        self.__instances = instances if instances is not None else []
        self.__instances_dict = {}
        self.__inst_lock = RLock()

    @property
    def instances(self):
        with self.__inst_lock:
            return self.__instances

    @property
    def up_instances(self):
        with self.__inst_lock:
            up_inst = []
            for item in self.__instances:
                if item.status == INSTANCE_STATUS_UP:
                    up_inst.append(item)
            return up_inst

    def get_instance(self, instance_id):
        with self.__inst_lock:
            if instance_id in self.__instances_dict:
                return self.__instances_dict[instance_id]
            else:
                return None

    def add_instance(self, instance):
        with self.__inst_lock:
            self.__instances.append(instance)
            self.__instances_dict[instance.instanceId] = instance

    def update_instance(self, instance):
        with self.__inst_lock:
            _logger.debug("update instance %s" % instance.instanceId)
            updated = False
            for idx in range(len(self.__instances)):
                ele = self.__instances[idx]
                if ele.instanceId == instance.instanceId:
                    _logger.debug("updating index %d" % idx)
                    self.__instances[idx] = instance
                    updated = True
                    break

            if not updated:
                self.add_instance(instance)

    def remove_instance(self, instance):
        with self.__inst_lock:
            for idx in range(len(self.__instances)):
                ele = self.__instances[idx]
                if ele.instanceId == instance.instanceId:
                    del self.__instances[idx]
                    break
            if instance.instanceId in self.__instances_dict:
                del self.__instances_dict[instance.instanceId]


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
                 className=_DEFAULT_DATA_CENTER_INFO_CLASS):
        self.name = name
        self.className = className


class PortWrapper:
    def __init__(self, port=0, enabled=False):
        self.port = port
        self.enabled = enabled


class Instance:

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
    _register(eureka_server, instance_dic)


def _register(eureka_server, instance_dic):
    req = http_client.Request(_format_url(eureka_server) + "apps/%s" % instance_dic["app"])
    req.add_header('Content-Type', 'application/json')
    req.get_method = lambda: "POST"
    http_client.load(req, json.dumps({"instance": instance_dic}).encode(_DEFAULT_ENCODING), timeout=_DEFAULT_TIME_OUT)


def cancel(eureka_server, app_name, instance_id):
    req = http_client.Request(_format_url(eureka_server) + "apps/%s/%s" % (app_name, instance_id))
    req.get_method = lambda: "DELETE"
    http_client.load(req, timeout=_DEFAULT_TIME_OUT)


def send_heart_beat(eureka_server, app_name, instance_id, last_dirty_timestamp, status=INSTANCE_STATUS_UP, overriddenstatus=""):
    #url = _format_url(eureka_server) + "apps/%s/%s?status=%s&lastDirtyTimestamp=%s" % \
    #    (app_name, instance_id, status, str(last_dirty_timestamp))
    url = _format_url(eureka_server) + "apps/%s/%s/status?value=%s&lastDirtyTimestamp=%s" % \
        (app_name, instance_id, status, str(last_dirty_timestamp))
    _logger.debug("heartbeat url::" + url)
    if overriddenstatus != "":
        url += "&overriddenstatus=" + overriddenstatus

    req = http_client.Request(url)
    req.get_method = lambda: "PUT"
    http_client.load(req, timeout=_DEFAULT_TIME_OUT)


def status_update(eureka_server, app_name, instance_id, last_dirty_timestamp, status):
    url = _format_url(eureka_server) + "apps/%s/%s?status=%s&lastDirtyTimestamp=%s" % \
        (app_name, instance_id, status, str(last_dirty_timestamp))

    req = http_client.Request(url)
    req.get_method = lambda: "PUT"
    http_client.load(req, timeout=_DEFAULT_TIME_OUT)


def delete_status_override(eureka_server, app_name, instance_id, last_dirty_timestamp):
    url = _format_url(eureka_server) + "apps/%s/%s/status?lastDirtyTimestamp=%s" % \
        (app_name, instance_id, str(last_dirty_timestamp))

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
    return _build_applications(ElementTree.fromstring(txt))


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
            instance.dataCenterInfo = DataCenterInfo(name=child_node.text, className=child_node.attrib["class"])
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


"""====================== Registry Client ======================================="""


class RegistryClient:
    """Eureka client for spring cloud"""

    def __init__(self,
                 eureka_server=_DEFAULT_EUREKA_SERVER_URL,
                 app_name="",
                 instance_id="",
                 instance_host="",
                 instance_ip="",
                 instance_port=_DEFAULT_INSTNACE_PORT,
                 instance_unsecure_port_enabled=True,
                 instance_secure_port=_DEFAULT_INSTNACE_SECURE_PORT,
                 instance_secure_port_enabled=False,
                 countryId=1,  # @deprecaded
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
        assert eureka_server is not None and eureka_server != "", "eureka server must be specified."
        assert app_name is not None and app_name != "", "application name must be specified."
        assert instance_port > 0, "port is unvalid"
        assert isinstance(metadata, dict), "metadata must be dict"

        self.__net_lock = RLock()
        self.__eureka_servers = eureka_server.split(",")

        def try_to_get_client_ip(url):
            if instance_host == "" and instance_ip == "":
                self.__instance_host = self.__instance_ip = RegistryClient.__get_instance_ip(url)
            elif instance_host != "" and instance_ip == "":
                self.__instance_host = instance_host
                if RegistryClient.__is_ip(instance_host):
                    self.__instance_ip = instance_host
                else:
                    self.__instance_ip = RegistryClient.__get_instance_ip(url)
            else:
                self.__instance_host = instance_ip
                self.__instance_ip = instance_ip

        self.__try_all_eureka_server(try_to_get_client_ip)

        mdata = {
            'management.port': str(instance_port)
        }
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
            'countryId': countryId,
            'dataCenterInfo': {
                '@class': _DEFAULT_DATA_CENTER_INFO_CLASS,
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
            'homePageUrl': RegistryClient.__format_url(home_page_url, self.__instance_host, instance_port),
            'statusPageUrl': RegistryClient.__format_url(status_page_url, self.__instance_host, instance_port, "info"),
            'healthCheckUrl': RegistryClient.__format_url(health_check_url, self.__instance_host, instance_port, "health"),
            'secureHealthCheckUrl': secure_health_check_url,
            'vipAddress': vip_adr if vip_adr != "" else app_name.lower(),
            'secureVipAddress': secure_vip_addr if secure_vip_addr != "" else app_name.lower(),
            'isCoordinatingDiscoveryServer': str(is_coordinating_discovery_server).lower()
        }

        self.__alive = False
        self.__heart_beat_timer = Timer(renewal_interval_in_secs, self.__heart_beat)
        self.__heart_beat_timer.daemon = True

    def __try_all_eureka_server(self, fun):
        with self.__net_lock:
            untry_servers = self.__eureka_servers
            tried_servers = []
            ok = False
            while len(untry_servers) > 0:
                url = untry_servers[0].strip()
                try:
                    fun(url)
                except (http_client.HTTPError, http_client.URLError):
                    _logger.warn("Eureka server [%s] is down, use next url to try." % url)
                    tried_servers.append(url)
                    untry_servers = untry_servers[1:]
                else:
                    ok = True
                    break
            if len(tried_servers) > 0:
                untry_servers.extend(tried_servers)
                self.__eureka_servers = untry_servers
            if not ok:
                raise http_client.URLError("All eureka servers are down!")

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
            self.__try_all_eureka_server(lambda url: _register(url, self.__instance))
        except:
            _logger.exception("error!")
        else:
            self.__alive = True

    def cancel(self):
        try:
            self.__try_all_eureka_server(lambda url: cancel(url, self.__instance["app"], self.__instance["instanceId"]))
        except:
            _logger.exception("error!")
        else:
            self.__alive = False

    def send_heart_beat(self, overridden_status=""):
        try:
            self.__try_all_eureka_server(lambda url: send_heart_beat(url, self.__instance["app"],
                                                                     self.__instance["instanceId"], self.__instance["lastDirtyTimestamp"],
                                                                     status=self.__instance["status"], overriddenstatus=overridden_status))
        except:
            _logger.exception("Error!")
            _logger.info("Cannot send heartbeat to server, try to register")
            self.register()

    def status_update(self, new_status):
        self.__instance["status"] = new_status
        try:
            self.__try_all_eureka_server(lambda url: status_update(url, self.__instance["app"], self.__instance["instanceId"],
                                                                   self.__instance["lastDirtyTimestamp"], new_status))
        except:
            _logger.exception("error!")

    def delete_status_override(self):
        self.__try_all_eureka_server(lambda url: delete_status_override(
            url, self.__instance["app"], self.__instance["instanceId"], self.__instance["lastDirtyTimestamp"]))

    def start(self):
        _logger.debug("start to registry client...")
        self.register()
        self.__heart_beat_timer.start()

    def stop(self):
        if self.__alive:
            _logger.debug("stopping client...")
            if self.__heart_beat_timer.isAlive():
                self.__heart_beat_timer.cancel()
            self.register(status=INSTANCE_STATUS_DOWN)
            self.cancel()

    def __heart_beat(self):
        while True:
            _logger.debug("sending heart beat to spring cloud server ")
            self.send_heart_beat()
            time.sleep(self.__instance["leaseInfo"]["renewalIntervalInSecs"])


__cache_key = "default"
__cache_registry_clients = {}
__cache_registry_clients_lock = RLock()


def init_registry_client(eureka_server=_DEFAULT_EUREKA_SERVER_URL,
                         app_name="",
                         instance_id="",
                         instance_host="",
                         instance_ip="",
                         instance_port=_DEFAULT_INSTNACE_PORT,
                         instance_unsecure_port_enabled=True,
                         instance_secure_port=_DEFAULT_INSTNACE_SECURE_PORT,
                         instance_secure_port_enabled=False,
                         countryId=1,  # @deprecaded
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
    with __cache_registry_clients_lock:
        client = RegistryClient(eureka_server=eureka_server,
                                app_name=app_name,
                                instance_id=instance_id,
                                instance_host=instance_host,
                                instance_ip=instance_ip,
                                instance_port=instance_port,
                                instance_unsecure_port_enabled=instance_unsecure_port_enabled,
                                instance_secure_port=instance_secure_port,
                                instance_secure_port_enabled=instance_secure_port_enabled,
                                countryId=countryId,
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
        __cache_registry_clients[__cache_key] = client
        client.start()
        return client


def get_registry_client():
    # type () -> RegistryClient
    with __cache_registry_clients_lock:
        if __cache_key in __cache_registry_clients:
            return __cache_registry_clients[__cache_key]
        else:
            return None


"""======================== Cached Discovery Client ============================"""


class DiscoveryClient:
    """Discover the apps registered in spring cloud server, this class will do some cached, if you want to get the apps immediatly, use the global functions"""

    def __init__(self, eureka_server, regions=None, renewal_interval_in_secs=_RENEWAL_INTERVAL_IN_SECS, ha_strategy=HA_STRATEGY_RANDOM):
        assert ha_strategy in [HA_STRATEGY_RANDOM, HA_STRATEGY_STICK, HA_STRATEGY_OTHER], "do not support strategy %d " % ha_strategy
        self.__eureka_servers = eureka_server.split(",")
        self.__regions = regions if regions is not None else []
        self.__cache_time_in_secs = renewal_interval_in_secs
        self.__applications = None
        self.__delta = None
        self.__ha_strategy = ha_strategy
        self.__ha_cache = {}
        self.__timer = Timer(self.__cache_time_in_secs, self.__heartbeat)
        self.__timer.daemon = True
        self.__application_mth_lock = RLock()
        self.__net_lock = RLock()

    def __heartbeat(self):
        while True:
            self.__fetch_delta()
            time.sleep(self.__cache_time_in_secs)

    @property
    def applications(self):
        with self.__application_mth_lock:
            if self.__applications is None:
                self.__pull_full_registry()
            return self.__applications

    def __try_all_eureka_server(self, fun):
        with self.__net_lock:
            untry_servers = self.__eureka_servers
            tried_servers = []
            ok = False
            while len(untry_servers) > 0:
                url = untry_servers[0].strip()
                try:
                    fun(url)
                except (http_client.HTTPError, http_client.URLError):
                    _logger.warn("Eureka server [%s] is down, use next url to try." % url)
                    tried_servers.append(url)
                    untry_servers = untry_servers[1:]
                else:
                    ok = True
                    break
            if len(tried_servers) > 0:
                untry_servers.extend(tried_servers)
                self.__eureka_servers = untry_servers
            if not ok:
                raise http_client.URLError("All eureka servers are down!")

    def __pull_full_registry(self):
        def do_pull(url):  # the actual function body
            self.__applications = get_applications(url, self.__regions)
            self.__delta = self.__applications
        self.__try_all_eureka_server(do_pull)

    def __fetch_delta(self):
        def do_fetch(url):
            if self.__applications is None or len(self.__applications.applications) == 0:
                self.__pull_full_registry()
                return
            delta = get_delta(url, self.__regions)
            _logger.debug("delta got: v.%s::%s" % (delta.versionsDelta, delta.appsHashcode))
            if self.__delta is not None \
                    and delta.versionsDelta == self.__delta.versionsDelta \
                    and delta.appsHashcode == self.__delta.appsHashcode:
                return
            self.__merge_delta(delta)
            self.__delta = delta
            if not self.__is_hash_match():
                self.__pull_full_registry()
        self.__try_all_eureka_server(do_fetch)

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
                _logger.debug("service url::" + url)
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

    def __get_available_service(self, application_name, ignore_instance_ids=None):
        app = self.applications.get_application(application_name)
        if app is None:
            return None
        up_instances = []
        if ignore_instance_ids is None or len(ignore_instance_ids) == 0:
            up_instances.extend(app.up_instances)
        else:
            for ins in app.up_instances:
                if ins.instanceId not in ignore_instance_ids:
                    up_instances.append(ins)

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

    def start(self):
        self.__pull_full_registry()
        self.__timer.start()

    def stop(self):
        if self.__timer.isAlive():
            self.__timer.cancel()


__cache_discovery_clients = {}
__cache_discovery_clients_lock = RLock()


def init_discovery_client(eureka_server=_DEFAULT_EUREKA_SERVER_URL, regions=[], renewal_interval_in_secs=_RENEWAL_INTERVAL_IN_SECS, ha_strategy=HA_STRATEGY_RANDOM):
    with __cache_discovery_clients_lock:
        assert __cache_key not in __cache_discovery_clients, "Client has already been initialized."
        cli = DiscoveryClient(eureka_server, regions=regions, renewal_interval_in_secs=renewal_interval_in_secs, ha_strategy=ha_strategy)
        cli.start()
        __cache_discovery_clients[__cache_key] = cli
        return cli


def get_discovery_client():
    # type: (str) -> DiscoveryClient
    with __cache_discovery_clients_lock:
        if __cache_key in __cache_discovery_clients:
            return __cache_discovery_clients[__cache_key]
        else:
            return None


def init(eureka_server=_DEFAULT_EUREKA_SERVER_URL,
         regions=[],
         app_name="",
         instance_id="",
         instance_host="",
         instance_ip="",
         instance_port=_DEFAULT_INSTNACE_PORT,
         instance_unsecure_port_enabled=True,
         instance_secure_port=_DEFAULT_INSTNACE_SECURE_PORT,
         instance_secure_port_enabled=False,
         countryId=1,  # @deprecaded
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
         ha_strategy=HA_STRATEGY_RANDOM):
    registry_client = init_registry_client(eureka_server=eureka_server,
                                           app_name=app_name,
                                           instance_id=instance_id,
                                           instance_host=instance_host,
                                           instance_ip=instance_ip,
                                           instance_port=instance_port,
                                           instance_unsecure_port_enabled=instance_unsecure_port_enabled,
                                           instance_secure_port=instance_secure_port,
                                           instance_secure_port_enabled=instance_secure_port_enabled,
                                           countryId=countryId,
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
    discovery_client = init_discovery_client(eureka_server,
                                             regions=regions,
                                             renewal_interval_in_secs=renewal_interval_in_secs,
                                             ha_strategy=ha_strategy)
    return registry_client, discovery_client


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
    register_cli = get_registry_client()
    if register_cli is not None:
        register_cli.stop()
    discovery_client = get_discovery_client()
    if discovery_client is not None:
        discovery_client.stop()


@atexit.register
def _cleanup_before_exist():
    if len(__cache_registry_clients) > 0:
        _logger.debug("cleaning up registry clients")
        for k, cli in __cache_registry_clients.items():
            _logger.debug("try to stop cache registry client [%s] this will also unregister this client from the eureka server" % k)
            cli.stop()
    if len(__cache_discovery_clients) > 0:
        _logger.debug("cleaning up discovery clients")
        for k, cli in __cache_discovery_clients.items():
            _logger.debug("try to stop cache discovery client [%s] this will also unregister this client from the eureka server" % k)
            cli.stop()
