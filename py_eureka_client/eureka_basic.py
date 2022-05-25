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


import json


from typing import Dict, List
import xml.etree.ElementTree as ElementTree
from threading import RLock
from urllib.parse import quote

import py_eureka_client.http_client as http_client

from py_eureka_client.logger import get_logger


from py_eureka_client import INSTANCE_STATUS_UP,   INSTANCE_STATUS_OUT_OF_SERVICE
from py_eureka_client import ACTION_TYPE_ADDED
from py_eureka_client import _DEFAULT_INSTNACE_PORT, _DEFAULT_INSTNACE_SECURE_PORT, _RENEWAL_INTERVAL_IN_SECS, _RENEWAL_INTERVAL_IN_SECS, _DURATION_IN_SECS, _DEFAULT_DATA_CENTER_INFO, _DEFAULT_DATA_CENTER_INFO_CLASS
from py_eureka_client import _DEFAULT_ENCODING, _DEFAUTL_ZONE, _DEFAULT_TIME_OUT

_logger = get_logger("eureka_basic")


### =========================> Base Mehods <======================================== ###
### Beans ###


class LeaseInfo:

    def __init__(self,
                 renewalIntervalInSecs: int = _RENEWAL_INTERVAL_IN_SECS,
                 durationInSecs: int = _DURATION_IN_SECS,
                 registrationTimestamp: int = 0,
                 lastRenewalTimestamp: int = 0,
                 renewalTimestamp: int = 0,
                 evictionTimestamp: int = 0,
                 serviceUpTimestamp: int = 0):
        self.renewalIntervalInSecs: int = renewalIntervalInSecs
        self.durationInSecs: int = durationInSecs
        self.registrationTimestamp: int = registrationTimestamp
        self.lastRenewalTimestamp: int = lastRenewalTimestamp
        self.renewalTimestamp: int = renewalTimestamp
        self.evictionTimestamp: int = evictionTimestamp
        self.serviceUpTimestamp: int = serviceUpTimestamp


class DataCenterInfo:

    def __init__(self,
                 name=_DEFAULT_DATA_CENTER_INFO,  # Netflix, Amazon, MyOwn
                 className=_DEFAULT_DATA_CENTER_INFO_CLASS,
                 metadata={}):
        self.name: str = name
        self.className: str = className
        self.metadata: Dict = metadata if metadata else {}


class PortWrapper:
    def __init__(self, port=0, enabled=False):
        self.port: int = port
        self.enabled: bool = enabled


class Instance:

    def __init__(self,
                 instanceId="",
                 sid="",  # @deprecated
                 app="",
                 appGroupName="",
                 ipAddr="",
                 port=PortWrapper(port=_DEFAULT_INSTNACE_PORT, enabled=True),
                 securePort=PortWrapper(
                     port=_DEFAULT_INSTNACE_SECURE_PORT, enabled=False),
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
        self.__instanceId: str = instanceId
        self.sid: str = sid
        self.app: str = app
        self.appGroupName: str = appGroupName
        self.ipAddr: str = ipAddr
        self.port: PortWrapper = port
        self.securePort: PortWrapper = securePort
        self.homePageUrl: str = homePageUrl
        self.statusPageUrl: str = statusPageUrl
        self.healthCheckUrl: str = healthCheckUrl
        self.secureHealthCheckUrl: str = secureHealthCheckUrl
        self.vipAddress: str = vipAddress
        self.secureVipAddress: str = secureVipAddress
        self.countryId: str = countryId
        self.dataCenterInfo: DataCenterInfo = dataCenterInfo
        self.hostName: str = hostName
        self.status: str = status
        self.overriddenstatus: str = overriddenstatus
        self.leaseInfo: LeaseInfo = leaseInfo
        self.isCoordinatingDiscoveryServer: bool = isCoordinatingDiscoveryServer
        self.metadata: Dict = metadata if metadata is not None else {}
        self.lastUpdatedTimestamp: int = lastUpdatedTimestamp
        self.lastDirtyTimestamp: int = lastDirtyTimestamp
        self.actionType: int = actionType
        self.asgName: int = asgName

    @property
    def instanceId(self):
        return self.__instanceId if self.__instanceId else f"{self.hostName}:{self.ipAddr}:{self.app}:{self.port.port if self.port else 0}"

    @instanceId.setter
    def instanceId(self, id):
        self.__instanceId = id

    @property
    def zone(self) -> str:
        if self.dataCenterInfo and self.dataCenterInfo.name == "Amazon" \
                and self.dataCenterInfo.metadata and "availability-zone" in self.dataCenterInfo.metadata:
            return self.dataCenterInfo.metadata["availability-zone"]
        if self.metadata and "zone" in self.metadata and self.metadata["zone"]:
            return self.metadata["zone"]
        else:
            return _DEFAUTL_ZONE


class Application:

    def __init__(self,
                 name="",
                 instances=None):
        self.name: str = name
        if isinstance(instances, list):
            for ins in instances:
                self.add_instance(ins)
        self.__instances_dict = {}
        self.__inst_lock = RLock()

    @property
    def instances(self) -> List[Instance]:
        with self.__inst_lock:
            return list(self.__instances_dict.values())

    @property
    def up_instances(self) -> List[Instance]:
        with self.__inst_lock:
            return [item for item in self.__instances_dict.values() if item.status == INSTANCE_STATUS_UP]

    def get_instance(self, instance_id: str) -> Instance:
        with self.__inst_lock:
            if instance_id in self.__instances_dict:
                return self.__instances_dict[instance_id]
            else:
                return None

    def add_instance(self, instance: Instance) -> None:
        with self.__inst_lock:
            self.__instances_dict[instance.instanceId] = instance

    def update_instance(self, instance: Instance) -> None:
        with self.__inst_lock:
            _logger.debug(f"update instance {instance.instanceId}")
            self.__instances_dict[instance.instanceId] = instance

    def remove_instance(self, instance: Instance) -> None:
        with self.__inst_lock:
            if instance.instanceId in self.__instances_dict:
                del self.__instances_dict[instance.instanceId]

    def up_instances_in_zone(self, zone: str) -> List[Instance]:
        with self.__inst_lock:
            _zone = zone if zone else _DEFAUTL_ZONE
            return [item for item in self.__instances_dict.values() if item.status == INSTANCE_STATUS_UP and item.zone == _zone]

    def up_instances_not_in_zone(self, zone: str) -> List[Instance]:
        with self.__inst_lock:
            _zone = zone if zone else _DEFAUTL_ZONE
            return [item for item in self.__instances_dict.values() if item.status == INSTANCE_STATUS_UP and item.zone != _zone]


class Applications:

    def __init__(self,
                 apps__hashcode="",
                 versions__delta="",
                 applications=None):
        self.apps__hashcode: str = apps__hashcode
        self.versions__delta: str = versions__delta
        self.__applications = applications if applications is not None else []
        self.__application_name_dic = {}
        self.__app_lock = RLock()

    @property
    def appsHashcode(self) -> str:
        return self.apps__hashcode

    @property
    def applications(self) -> List[Application]:
        return self.__applications

    @property
    def versionsDelta(self) -> str:
        return self.versions__delta

    def add_application(self, application: Application) -> None:
        with self.__app_lock:
            self.__applications.append(application)
            self.__application_name_dic[application.name] = application

    def get_application(self, app_name: str = "") -> Application:
        with self.__app_lock:
            aname = app_name.upper()
            if app_name in self.__application_name_dic:
                return self.__application_name_dic[aname]
            else:
                return Application(name=aname)


########################## Basic functions #################################
####### Registry functions #########
async def register(eureka_server: str, instance: Instance) -> None:
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
    await _register(eureka_server, instance_dic)


async def _register(eureka_server: str, instance_dic: Dict) -> None:
    req = http_client.HttpRequest(f"{_format_url(eureka_server)}apps/{quote(instance_dic['app'])}",
                                  method="POST",
                                  headers={"Content-Type": "application/json"})
    await http_client.http_client.urlopen(req, json.dumps({"instance": instance_dic}).encode(
        _DEFAULT_ENCODING), timeout=_DEFAULT_TIME_OUT)


async def cancel(eureka_server: str, app_name: str, instance_id: str) -> None:
    req = http_client.HttpRequest(f"{_format_url(eureka_server)}apps/{quote(app_name)}/{quote(instance_id)}",
                                  method="DELETE")
    await http_client.http_client.urlopen(req, timeout=_DEFAULT_TIME_OUT)


async def send_heartbeat(eureka_server: str,
                         app_name: str,
                         instance_id: str,
                         last_dirty_timestamp: int,
                         status: str = INSTANCE_STATUS_UP,
                         overriddenstatus: str = "") -> None:
    url = f"{_format_url(eureka_server)}apps/{quote(app_name)}/{quote(instance_id)}?status={status}&lastDirtyTimestamp={last_dirty_timestamp}"
    if overriddenstatus != "":
        url += f"&overriddenstatus={overriddenstatus}"

    req = http_client.HttpRequest(url, method="PUT")
    await http_client.http_client.urlopen(req, timeout=_DEFAULT_TIME_OUT)


async def status_update(eureka_server: str,
                        app_name: str,
                        instance_id: str,
                        last_dirty_timestamp,
                        status: str = INSTANCE_STATUS_OUT_OF_SERVICE,
                        overriddenstatus: str = ""):
    url = f"{_format_url(eureka_server)}apps/{quote(app_name)}/{quote(instance_id)}/status?value={status}&lastDirtyTimestamp={last_dirty_timestamp}"
    if overriddenstatus != "":
        url += f"&overriddenstatus={overriddenstatus}"

    req = http_client.HttpRequest(url, method="PUT")
    await http_client.http_client.urlopen(req, timeout=_DEFAULT_TIME_OUT)


async def delete_status_override(eureka_server: str, app_name: str, instance_id: str, last_dirty_timestamp: str):
    url = f"{_format_url(eureka_server)}apps/{quote(app_name)}/{quote(instance_id)}/status?lastDirtyTimestamp={last_dirty_timestamp}"

    req = http_client.HttpRequest(url, method="DELETE")
    await http_client.http_client.urlopen(req, timeout=_DEFAULT_TIME_OUT)


####### Discovory functions ########


async def get_applications(eureka_server: str, regions: List[str] = []) -> Applications:
    res = await _get_applications_(f"{_format_url(eureka_server)}apps/", regions)
    return res


def _format_url(url):
    if url.endswith('/'):
        return url
    else:
        return url + "/"


async def _get_applications_(url, regions=[]):
    _url = url
    if len(regions) > 0:
        _url = _url + ("&" if "?" in _url else "?") + \
            "regions=" + (",".join(regions))

    res = await http_client.http_client.urlopen(
        _url, timeout=_DEFAULT_TIME_OUT)
    return _build_applications(ElementTree.fromstring(res.body_text.encode(_DEFAULT_ENCODING)))


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
            instance.isCoordinatingDiscoveryServer = (
                child_node.text == "true")
        elif child_node.tag == "metadata":
            instance.metadata = _build_metadata(child_node)
        elif child_node.tag == "lastUpdatedTimestamp":
            instance.lastUpdatedTimestamp = int(child_node.text)
        elif child_node.tag == "lastDirtyTimestamp":
            instance.lastDirtyTimestamp = int(child_node.text)
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
            leaseInfo.registrationTimestamp = int(child_node.text)
        elif child_node.tag == "lastRenewalTimestamp":
            leaseInfo.lastRenewalTimestamp = int(child_node.text)
        elif child_node.tag == "renewalTimestamp":
            leaseInfo.renewalTimestamp = int(child_node.text)
        elif child_node.tag == "evictionTimestamp":
            leaseInfo.evictionTimestamp = int(child_node.text)
        elif child_node.tag == "serviceUpTimestamp":
            leaseInfo.serviceUpTimestamp = int(child_node.text)

    return leaseInfo


def _build_port(xml_node):
    port = PortWrapper()
    port.port = int(xml_node.text)
    port.enabled = (xml_node.attrib["enabled"] == "true")
    return port


async def get_delta(eureka_server: str, regions: List[str] = []) -> Applications:
    res = await _get_applications_(f"{_format_url(eureka_server)}apps/delta", regions)
    return res


async def get_vip(eureka_server: str, vip: str, regions: List[str] = []) -> Applications:
    res = await _get_applications_(f"{_format_url(eureka_server)}vips/{vip}", regions)
    return res


async def get_secure_vip(eureka_server: str, svip: str, regions: List[str] = []) -> Applications:
    res = await _get_applications_(f"{_format_url(eureka_server)}svips/{svip}", regions)
    return res


async def get_application(eureka_server: str, app_name: str) -> Application:
    url = f"{_format_url(eureka_server)}apps/{quote(app_name)}"
    res = await http_client.http_client.urlopen(url, timeout=_DEFAULT_TIME_OUT)
    return _build_application(ElementTree.fromstring(res.body_text))


async def get_app_instance(eureka_server: str, app_name: str, instance_id: str) -> Instance:
    res = await _get_instance_(f"{_format_url(eureka_server)}apps/{quote(app_name)}/{quote(instance_id)}")
    return res


async def get_instance(eureka_server: str, instance_id: str) -> Instance:
    res = _get_instance_(
        f"{_format_url(eureka_server)}instances/{quote(instance_id)}")
    return res


async def _get_instance_(url):
    res = await http_client.http_client.urlopen(
        url, timeout=_DEFAULT_TIME_OUT)
    return _build_instance(ElementTree.fromstring(res.body_text))
