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


import asyncio

import json
import re
import socket
import threading
import time

import random

from copy import copy
from typing import Callable, Dict, List, Union
from threading import RLock, Timer
from urllib.parse import quote

import py_eureka_client.http_client as http_client
import py_eureka_client.netint_utils as netint
from py_eureka_client.logger import get_logger
from py_eureka_client.__dns_txt_resolver import get_txt_dns_record
from py_eureka_client.__aws_info_loader import AmazonInfo

from py_eureka_client import INSTANCE_STATUS_UP, INSTANCE_STATUS_DOWN, INSTANCE_STATUS_STARTING, INSTANCE_STATUS_OUT_OF_SERVICE, INSTANCE_STATUS_UNKNOWN
from py_eureka_client import ACTION_TYPE_ADDED, ACTION_TYPE_MODIFIED, ACTION_TYPE_DELETED
from py_eureka_client import HA_STRATEGY_RANDOM, HA_STRATEGY_STICK, HA_STRATEGY_OTHER
from py_eureka_client import ERROR_REGISTER, ERROR_DISCOVER, ERROR_STATUS_UPDATE
from py_eureka_client import _DEFAULT_EUREKA_SERVER_URL, _DEFAULT_INSTNACE_PORT, _DEFAULT_INSTNACE_SECURE_PORT, _RENEWAL_INTERVAL_IN_SECS, _RENEWAL_INTERVAL_IN_SECS, _DURATION_IN_SECS, _DEFAULT_DATA_CENTER_INFO, _DEFAULT_DATA_CENTER_INFO_CLASS, _AMAZON_DATA_CENTER_INFO_CLASS
from py_eureka_client import _DEFAUTL_ZONE, _DEFAULT_TIME_OUT

from py_eureka_client.eureka_basic import LeaseInfo, DataCenterInfo, PortWrapper, Instance, Application, Applications
from py_eureka_client.eureka_basic import register, _register, cancel, send_heartbeat, status_update, delete_status_override
from py_eureka_client.eureka_basic import get_applications, get_delta, get_vip, get_secure_vip, get_application, get_app_instance, get_instance

_logger = get_logger("eureka_client")


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
        self.region: str = region
        self.__zone = zone
        self.__eureka_availability_zones: dict = eureka_availability_zones
        _zone = zone if zone else _DEFAUTL_ZONE
        if eureka_domain:
            zone_urls = get_txt_dns_record(f"txt.{region}.{eureka_domain}")
            for zone_url in zone_urls:
                zone_name = zone_url.split(".")[0]
                eureka_urls = get_txt_dns_record(f"txt.{zone_url}")
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
    def zone(self) -> str:
        if self.__zone:
            return self.__zone
        elif self.__eureka_availability_zones:
            return list(self.__eureka_availability_zones.keys())[0]
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
                basic_auth = f"{user}:{password}"
            else:
                basic_auth = user
            basic_auth += "@"

        if url.find("/") > 0:
            ctx = ""
        else:
            ctx = eureka_context if eureka_context.startswith(
                '/') else "/" + eureka_context

        return f"{prtl}://{basic_auth}{url}{ctx}"

    @property
    def servers(self) -> Dict:
        return self.__servers

    @property
    def servers_in_zone(self) -> List[str]:
        if self.zone in self.servers:
            return self.servers[self.zone]
        else:
            return []

    @property
    def servers_not_in_zone(self) -> List[str]:
        return self.__servers_not_in_zone


class EurekaServerConnectionException(http_client.URLError):
    pass


class DiscoverException(http_client.URLError):
    pass


class EurekaClient:
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

    You can use `do_service`, `wall_nodes` to call the remote services.

    >>> res = eureka_client.do_service("OTHER-SERVICE-NAME", "/service/context/path")

    >>> def walk_using_your_own_urllib(url):
            ...

        res = await client.walk_nodes("OTHER-SERVICE-NAME", "/service/context/path", walker=walk_using_your_own_urllib)


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

    * instance_host: The host of this instance. 

    * instance_ip: The ip of this instance. If instance_host and instance_ip are not specified, will try to find the ip via connection to the eureka server.

    * instance_ip_network: The ip network of this instance. If instance_host and instance_ip are not specified, will try to find the ip from the avaiable network adapters that matches the specified network. For example 192.168.1.0/24.

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

    * strict_service_error_policy: When set to True, all error(Including connection error and HttpError, like http 
        status code is not 200) will consider as error; Otherwise, only (ConnectionError, TimeoutError, socket.timeout) 
        will be considered as error, and other excptions and errors will be raised to upstream. Default is True.

    """

    def __init__(self,
                 eureka_server: str = _DEFAULT_EUREKA_SERVER_URL,
                 eureka_domain: str = "",
                 region: str = "",
                 zone: str = "",
                 eureka_availability_zones: Dict[str, str] = {},
                 eureka_protocol: str = "http",
                 eureka_basic_auth_user: str = "",
                 eureka_basic_auth_password: str = "",
                 eureka_context: str = "/eureka",
                 prefer_same_zone: bool = True,
                 should_register: bool = True,
                 should_discover: bool = True,
                 on_error: Callable = None,
                 app_name: str = "",
                 instance_id: str = "",
                 instance_host: str = "",
                 instance_ip: str = "",
                 instance_ip_network: str = "",
                 instance_port: int = _DEFAULT_INSTNACE_PORT,
                 instance_unsecure_port_enabled: bool = True,
                 instance_secure_port: int = _DEFAULT_INSTNACE_SECURE_PORT,
                 instance_secure_port_enabled: bool = False,
                 data_center_name: str = _DEFAULT_DATA_CENTER_INFO,  # Netflix, Amazon, MyOwn
                 renewal_interval_in_secs: int = _RENEWAL_INTERVAL_IN_SECS,
                 duration_in_secs: int = _DURATION_IN_SECS,
                 home_page_url: str = "",
                 status_page_url: str = "",
                 health_check_url: str = "",
                 secure_health_check_url: str = "",
                 vip_adr: str = "",
                 secure_vip_addr: str = "",
                 is_coordinating_discovery_server: bool = False,
                 metadata: Dict = {},
                 remote_regions: List[str] = [],
                 ha_strategy: int = HA_STRATEGY_RANDOM,
                 strict_service_error_policy: bool = True):
        assert app_name is not None and app_name != "" if should_register else True, "application name must be specified."
        assert instance_port > 0 if should_register else True, "port is unvalid"
        assert isinstance(metadata, dict), "metadata must be dict"
        assert ha_strategy in (HA_STRATEGY_RANDOM, HA_STRATEGY_STICK,
                               HA_STRATEGY_OTHER) if should_discover else True, f"do not support strategy {ha_strategy}"

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
        self.__heartbeat_interval = renewal_interval_in_secs
        self.__heartbeat_timer = Timer(self.__heartbeat_interval, self.__heartbeat_thread)
        self.__heartbeat_timer.setName("HeartbeatThread")
        self.__heartbeat_timer.daemon = True

        self.__instance_id = instance_id
        self.__instance_ip = instance_ip
        self.__instance_ip_network = instance_ip_network
        self.__instance_host = instance_host
        self.__instance_port = instance_port
        self.__app_name = app_name
        self.__instance_unsecure_port_enabled = instance_unsecure_port_enabled
        self.__instance_secure_port = instance_secure_port
        self.__instance_secure_port_enabled = instance_secure_port_enabled
        self.__data_center_name = data_center_name
        self.__duration_in_secs = duration_in_secs
        self.__metadata = metadata
        self.__home_page_url = home_page_url
        self.__status_page_url = status_page_url
        self.__health_check_url = health_check_url
        self.__secure_health_check_url = secure_health_check_url
        self.__vip_adr = vip_adr
        self.__secure_vip_addr = secure_vip_addr
        self.__is_coordinating_discovery_server = is_coordinating_discovery_server

        self.__aws_metadata = {}
        self.__on_error_callback = on_error

        # For Registery
        self.__instance = {}

        # For discovery
        self.__remote_regions = remote_regions if remote_regions is not None else []
        self.__applications = None
        self.__delta = None
        self.__ha_strategy = ha_strategy
        self.__strict_service_error_policy = strict_service_error_policy
        self.__ha_cache = {}

        self.__application_mth_lock = RLock()

    async def __parepare_instance_info(self):
        if self.__data_center_name == "Amazon":
            self.__aws_metadata = await self.__load_ec2_metadata_dict()
        if self.__instance_host == "" and self.__instance_ip == "":
            self.__instance_ip, self.__instance_host = self.__get_ip_host(
                self.__instance_ip_network)
        elif self.__instance_host != "" and self.__instance_ip == "":
            self.__instance_ip = netint.get_ip_by_host(
                self.__instance_host)
            if not EurekaClient.__is_ip(self.__instance_ip):
                async def try_to_get_client_ip(url):
                    self.__instance_ip = EurekaClient.__get_instance_ip(url)
                await self.__connect_to_eureka_server(try_to_get_client_ip)
        elif self.__instance_host == "" and self.__instance_ip != "":
            self.__instance_host = netint.get_host_by_ip(self.__instance_ip)

        mdata = {
            'management.port': str(self.__instance_port)
        }
        if self.__eureka_server_conf.zone:
            mdata["zone"] = self.__eureka_server_conf.zone
        mdata.update(self.__metadata)
        ins_id = self.__instance_id or f"{self.__instance_ip}:{self.__app_name.lower()}:{self.__instance_port}"
        _logger.debug(f"register instance using id [#{ins_id}]")
        self.__instance = {
            'instanceId': ins_id,
            'hostName': self.__instance_host,
            'app': self.__app_name.upper(),
            'ipAddr': self.__instance_ip,
            'port': {
                '$': self.__instance_port,
                '@enabled': str(self.__instance_unsecure_port_enabled).lower()
            },
            'securePort': {
                '$': self.__instance_secure_port,
                '@enabled': str(self.__instance_secure_port_enabled).lower()
            },
            'countryId': 1,
            'dataCenterInfo': {
                '@class': _AMAZON_DATA_CENTER_INFO_CLASS if self.__data_center_name == "Amazon" else _DEFAULT_DATA_CENTER_INFO_CLASS,
                'name': self.__data_center_name
            },
            'leaseInfo': {
                'renewalIntervalInSecs': self.__heartbeat_interval,
                'durationInSecs': self.__duration_in_secs,
                'registrationTimestamp': 0,
                'lastRenewalTimestamp': 0,
                'evictionTimestamp': 0,
                'serviceUpTimestamp': 0
            },
            'metadata': mdata,
            'homePageUrl': EurekaClient.__format_url(self.__home_page_url, self.__instance_host, self.__instance_port),
            'statusPageUrl': EurekaClient.__format_url(self.__status_page_url, self.__instance_host, self.__instance_port, "info"),
            'healthCheckUrl': EurekaClient.__format_url(self.__health_check_url, self.__instance_host, self.__instance_port, "health"),
            'secureHealthCheckUrl': self.__secure_health_check_url,
            'vipAddress': self.__vip_adr or self.__app_name.lower(),
            'secureVipAddress': self.__secure_vip_addr or self.__app_name.lower(),
            'isCoordinatingDiscoveryServer': str(self.__is_coordinating_discovery_server).lower()
        }
        if self.__data_center_name == "Amazon":
            self.__instance["dataCenterInfo"]["metadata"] = self.__aws_metadata

    def __get_ip_host(self, network):
        ip, host = netint.get_ip_and_host(network)
        if self.__aws_metadata and "local-ipv4" in self.__aws_metadata and self.__aws_metadata["local-ipv4"]:
            ip = self.__aws_metadata["local-ipv4"]
        if self.__aws_metadata and "local-hostname" in self.__aws_metadata and self.__aws_metadata["local-hostname"]:
            host = self.__aws_metadata["local-hostname"]
        return ip, host

    async def __load_ec2_metadata_dict(self):
        # instance metadata
        amazon_info = AmazonInfo()
        mac = await amazon_info.get_ec2_metadata('mac')
        if mac:
            vpc_id = await amazon_info.get_ec2_metadata(
                f'network/interfaces/macs/{mac}/vpc-id')
        else:
            vpc_id = ""
        metadata = {
            'instance-id': amazon_info.get_ec2_metadata('instance-id'),
            'ami-id': amazon_info.get_ec2_metadata('ami-id'),
            'instance-type': amazon_info.get_ec2_metadata('instance-type'),
            'local-ipv4': amazon_info.get_ec2_metadata('local-ipv4'),
            'local-hostname': amazon_info.get_ec2_metadata('local-hostname'),
            'availability-zone': amazon_info.get_ec2_metadata('placement/availability-zone', ignore_error=True),
            'public-hostname': amazon_info.get_ec2_metadata('public-hostname', ignore_error=True),
            'public-ipv4': amazon_info.get_ec2_metadata('public-ipv4', ignore_error=True),
            'mac': mac,
            'vpcId': vpc_id
        }
        # accountId
        doc = await amazon_info.get_instance_identity_document()
        if doc and "accountId" in doc:
            metadata["accountId"] = doc["accountId"]
        return metadata

    @property
    def should_register(self) -> bool:
        return self.__should_register

    @property
    def should_discover(self) -> bool:
        return self.__should_discover

    @property
    def zone(self) -> str:
        return self.__eureka_server_conf.zone

    @property
    def applications(self) -> Applications:
        if not self.should_discover:
            raise DiscoverException(
                "should_discover set to False, no registry is pulled, cannot find any applications.")
        with self.__application_mth_lock:
            if self.__applications is None:
                self.__pull_full_registry()
            return self.__applications

    async def __try_eureka_server_in_cache(self, fun):
        ok = False
        invalid_keys = []
        for z, url in self.__cache_eureka_url.items():
            try:
                _logger.debug(
                    f"Try to do {fun.__name__} in zone[{z}] using cached url {url}. ")
                await fun(url)
            except (http_client.HTTPError, http_client.URLError):
                _logger.warn(
                    f"Eureka server [{url}] is down, use next url to try.", exc_info=True)
                invalid_keys.append(z)
            else:
                ok = True
        if invalid_keys:
            _logger.debug(
                f"Invalid keys::{invalid_keys} will be removed from cache.")
            for z in invalid_keys:
                del self.__cache_eureka_url[z]
        if not ok:
            raise EurekaServerConnectionException(
                "All eureka servers in cache are down!")

    async def __try_eureka_server_in_zone(self, fun):
        await self.__try_eureka_servers_in_list(
            fun, self.__eureka_server_conf.servers_in_zone, self.zone)

    async def __try_eureka_server_not_in_zone(self, fun):
        for zone, urls in self.__eureka_server_conf.servers_not_in_zone.items():
            try:
                await self.__try_eureka_servers_in_list(fun, urls, zone)
            except EurekaServerConnectionException:
                _logger.warn(
                    f"try eureka servers in zone[{zone}] error!", exc_info=True)
            else:
                return
        raise EurekaServerConnectionException(
            "All eureka servers in all zone are down!")

    async def __try_eureka_server_regardless_zones(self, fun):
        for zone, urls in self.__eureka_server_conf.servers.items():
            try:
                await self.__try_eureka_servers_in_list(fun, urls, zone)
            except EurekaServerConnectionException:
                _logger.warn(
                    f"try eureka servers in zone[{zone}] error!", exc_info=True)
            else:
                return
        raise EurekaServerConnectionException(
            "All eureka servers in all zone are down!")

    async def __try_all_eureka_servers(self, fun):
        if self.__prefer_same_zone:
            try:
                await self.__try_eureka_server_in_zone(fun)
            except EurekaServerConnectionException:
                await self.__try_eureka_server_not_in_zone(fun)
        else:
            await self.__try_eureka_server_regardless_zones(fun)

    async def __try_eureka_servers_in_list(self, fun, eureka_servers=[], zone=_DEFAUTL_ZONE):
        with self.__net_lock:
            ok = False
            _zone = zone if zone else _DEFAUTL_ZONE
            for url in eureka_servers:
                url = url.strip()
                try:
                    _logger.debug(
                        f"try to do {fun.__name__} in zone[{_zone}] using url {url}. ")
                    await fun(url)
                except (http_client.HTTPError, http_client.URLError):
                    _logger.warn(
                        f"Eureka server [{url}] is down, use next url to try.", exc_info=True)
                else:
                    ok = True
                    self.__cache_eureka_url[_zone] = url
                    break

            if not ok:
                if _zone in self.__cache_eureka_url:
                    del self.__cache_eureka_url[_zone]
                raise EurekaServerConnectionException(
                    f"All eureka servers in zone[{_zone}] are down!")

    async def __connect_to_eureka_server(self, fun):
        if self.__cache_eureka_url:
            try:
                await self.__try_eureka_server_in_cache(fun)
            except EurekaServerConnectionException:
                await self.__try_all_eureka_servers(fun)
        else:
            await self.__try_all_eureka_servers(fun)

    @staticmethod
    def __format_url(url: str, host: str, port: str, defalut_ctx=""):
        if url != "":
            if url.startswith('http'):
                _url = url
            elif url.startswith('/'):
                _url = f'http://{host}:{port}{url}'
            else:
                _url = f'http://{host}:{port}/{url}'
        else:
            _url = f'http://{host}:{port}/{defalut_ctx}'
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

    async def _on_error(self, error_type: str, exception: Exception):
        if self.__on_error_callback:
            if asyncio.iscoroutine(self.__on_error_callback):
                await self.__on_error_callback(error_type, exception)
            elif callable(self.__on_error_callback):
                self.__on_error_callback(error_type, exception)

    async def register(self, status: str = INSTANCE_STATUS_UP, overriddenstatus: str = INSTANCE_STATUS_UNKNOWN) -> None:
        self.__instance["status"] = status
        self.__instance["overriddenstatus"] = overriddenstatus
        self.__instance["lastUpdatedTimestamp"] = str(_current_time_millis())
        self.__instance["lastDirtyTimestamp"] = str(_current_time_millis())
        try:
            async def do_register(url):
                await _register(url, self.__instance)
            await self.__connect_to_eureka_server(do_register)
        except Exception as e:
            self.__alive = False
            _logger.warn(
                "Register error! Will try in next heartbeat. ", exc_info=True)
            await self._on_error(ERROR_REGISTER, e)
        else:
            _logger.debug("register successfully!")
            self.__alive = True

    async def cancel(self) -> None:
        try:
            async def do_cancel(url):
                await cancel(url, self.__instance["app"],
                             self.__instance["instanceId"])
            await self.__connect_to_eureka_server(do_cancel)
        except Exception as e:
            _logger.warn("Cancel error!", exc_info=True)
            await self._on_error(ERROR_STATUS_UPDATE, e)
        else:
            self.__alive = False

    async def send_heartbeat(self, overridden_status: str = "") -> None:
        if not self.__alive:
            await self.register()
            return
        try:
            _logger.debug("sending heartbeat to eureka server. ")

            async def do_send_heartbeat(url):
                await send_heartbeat(url, self.__instance["app"],
                                     self.__instance["instanceId"], self.__instance["lastDirtyTimestamp"],
                                     status=self.__instance["status"], overriddenstatus=overridden_status)
            await self.__connect_to_eureka_server(do_send_heartbeat)
        except Exception as e:
            _logger.warn(
                "Cannot send heartbeat to server, try to register. ", exc_info=True)
            await self._on_error(ERROR_STATUS_UPDATE, e)
            await self.register()

    async def status_update(self, new_status: str) -> None:
        self.__instance["status"] = new_status
        try:
            async def do_status_update(url):
                await status_update(url, self.__instance["app"], self.__instance["instanceId"],
                                    self.__instance["lastDirtyTimestamp"], new_status)
            await self.__connect_to_eureka_server(do_status_update)
        except Exception as e:
            _logger.warn("update status error!", exc_info=True)
            await self._on_error(ERROR_STATUS_UPDATE, e)

    async def delete_status_override(self) -> None:
        try:
            async def do_delete_status_override(url):
                await delete_status_override(
                    url, self.__instance["app"], self.__instance["instanceId"], self.__instance["lastDirtyTimestamp"])
            await self.__connect_to_eureka_server(do_delete_status_override)
        except Exception as e:
            _logger.warn("delete status overrid error!", exc_info=True)
            await self._on_error(ERROR_STATUS_UPDATE, e)

    async def __start_register(self):
        _logger.debug("start to registry client...")
        await self.register()

    async def __stop_registery(self):
        if self.__alive:
            await self.register(status=INSTANCE_STATUS_DOWN)
            await self.cancel()

    def __heartbeat_thread(self):
        _logger.debug("Start heartbeat!")
        loop = asyncio.new_event_loop()
        while True:
            loop.run_until_complete(self.__heartbeat())
            time.sleep(self.__heartbeat_interval)

    async def __heartbeat(self):
        if self.__should_register:
            _logger.debug("sending heartbeat to eureka server ")
            await self.send_heartbeat()
        if self.__should_discover:
            _logger.debug("loading services from  eureka server")
            await self.__fetch_delta()

    async def __pull_full_registry(self):
        async def do_pull(url):  # the actual function body
            self.__applications = await get_applications(url, self.__remote_regions)
            self.__delta = self.__applications
        try:
            await self.__connect_to_eureka_server(do_pull)
        except Exception as e:
            _logger.warn(
                "pull full registry from eureka server error!", exc_info=True)
            await self._on_error(ERROR_DISCOVER, e)

    async def __fetch_delta(self):
        async def do_fetch(url):
            if self.__applications is None or len(self.__applications.applications) == 0:
                await self.__pull_full_registry()
                return
            delta = await get_delta(url, self.__remote_regions)
            _logger.debug(
                f"delta got: v.{delta.versionsDelta}::{delta.appsHashcode}")
            if self.__delta is not None \
                    and delta.versionsDelta == self.__delta.versionsDelta \
                    and delta.appsHashcode == self.__delta.appsHashcode:
                return
            self.__merge_delta(delta)
            self.__delta = delta
            if not self.__is_hash_match():
                await self.__pull_full_registry()
        try:
            await self.__connect_to_eureka_server(do_fetch)
        except Exception as e:
            _logger.warn(
                "fetch delta from eureka server error!", exc_info=True)
            await self._on_error(ERROR_DISCOVER, e)

    def __is_hash_match(self):
        app_hash = self.__get_applications_hash()
        _logger.debug(
            f"check hash, local[{app_hash}], remote[{self.__delta.appsHashcode}]")
        return app_hash == self.__delta.appsHashcode

    def __merge_delta(self, delta):
        _logger.debug(
            f"merge delta...length of application got from delta::{len(delta.applications)}")
        for application in delta.applications:
            for instance in application.instances:
                _logger.debug(
                    f"instance [{instance.instanceId}] has {instance.actionType}")
                if instance.actionType in (ACTION_TYPE_ADDED, ACTION_TYPE_MODIFIED):
                    existingApp = self.applications.get_application(
                        application.name)
                    if existingApp is None:
                        self.applications.add_application(application)
                    else:
                        existingApp.update_instance(instance)
                elif instance.actionType == ACTION_TYPE_DELETED:
                    existingApp = self.applications.get_application(
                        application.name)
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
                app_status_count[instance.status.upper(
                )] = app_status_count[instance.status.upper()] + 1

        sorted_app_status_count = sorted(
            app_status_count.items(), key=lambda item: item[0])
        for item in sorted_app_status_count:
            app_hash = f"{app_hash}{item[0]}_{item[1]}_"
        return app_hash

    async def walk_nodes(self,
                         app_name: str = "",
                         service: str = "",
                         prefer_ip: bool = False,
                         prefer_https: bool = False,
                         walker: Callable = None) -> Union[str, Dict, http_client.HttpResponse]:
        assert app_name is not None and app_name != "", "application_name should not be null"

        error_nodes = []
        app_name = app_name.upper()
        node = self.__get_available_service(app_name)

        while node is not None:
            try:
                url = self.__generate_service_url(
                    node, prefer_ip, prefer_https)
                if service.startswith("/"):
                    url = url + service[1:]
                else:
                    url = url + service
                _logger.debug("do service with url::" + url)
                obj = walker(url)
                if asyncio.iscoroutine(obj):
                    return await obj
                else:
                    return obj
            except (ConnectionError, TimeoutError, socket.timeout) as e:
                _logger.warning(
                    f"do service {service} in node [{node.instanceId}] error, use next node. Error: {e}")
                error_nodes.append(node.instanceId)
                node = self.__get_available_service(app_name, error_nodes)
            except (http_client.HTTPError, http_client.URLError) as e:
                if self.__strict_service_error_policy:
                    _logger.warning(
                        f"do service {service} in node [{node.instanceId}] error, use next node. Error: {e}")
                    error_nodes.append(node.instanceId)
                    node = self.__get_available_service(app_name, error_nodes)
                else:
                    raise e

        raise http_client.URLError(
            "Try all up instances in registry, but all fail")

    async def do_service(self, app_name: str = "", service: str = "", return_type: str = "string",
                         prefer_ip: bool = False, prefer_https: bool = False,
                         method: str = "GET", headers: Dict[str, str] = None,
                         data: Union[bytes, str, Dict] = None, timeout: float = _DEFAULT_TIME_OUT
                         ) -> Union[str, Dict, http_client.HttpResponse]:
        if data and isinstance(data, dict):
            _data = json.dumps(data).encode()
        elif data and isinstance(data, str):
            _data = data.encode()
        else:
            _data = data

        async def walk_using_urllib(url):
            req = http_client.HttpRequest(url, method=method, headers=headers)

            res: http_client.HttpResponse = await http_client.http_client.urlopen(
                req, data=_data, timeout=timeout)
            if return_type.lower() in ("json", "dict", "dictionary"):
                return json.loads(res.body_text)
            elif return_type.lower() == "response_object":
                return res.raw_response
            else:
                return res.body_text
        return await self.walk_nodes(app_name, service, prefer_ip, prefer_https, walk_using_urllib)

    def __get_service_not_in_ignore_list(self, instances, ignores):
        ign = ignores if ignores else []
        return [item for item in instances if item.instanceId not in ign]

    def __get_available_service(self, application_name, ignore_instance_ids=None):
        apps = self.applications
        if not apps:
            raise DiscoverException(
                "Cannot load registry from eureka server, please check your configurations. ")
        app = apps.get_application(application_name)
        if app is None:
            return None
        up_instances = []
        if self.__prefer_same_zone:
            ups_same_zone = app.up_instances_in_zone(self.zone)
            up_instances = self.__get_service_not_in_ignore_list(
                ups_same_zone, ignore_instance_ids)
            if not up_instances:
                ups_not_same_zone = app.up_instances_not_in_zone(self.zone)
                _logger.debug(
                    f"app[{application_name}]'s up instances not in same zone are all down, using the one that's not in the same zone: {[ins.instanceId for ins in ups_not_same_zone]}")
                up_instances = self.__get_service_not_in_ignore_list(
                    ups_not_same_zone, ignore_instance_ids)
        else:
            up_instances = self.__get_service_not_in_ignore_list(
                app.up_instances, ignore_instance_ids)

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

    def __generate_service_url(self, instance: Instance, prefer_ip, prefer_https):
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

        if (schema == "http" and port == 80) or (schema == 'https' and port == 443):
            return f"{schema}://{host}/"
        else:
            return f"{schema}://{host}:{port}/"

    async def __start_discover(self):
        await self.__pull_full_registry()

    async def start(self) -> None:
        if self.should_register:
            await self.__parepare_instance_info()
            await self.__start_register()
        if self.should_discover:
            await self.__start_discover()
        self.__heartbeat_timer.start()

    async def stop(self) -> None:
        if self.__heartbeat_timer.is_alive():
            self.__heartbeat_timer.cancel()
        if self.__should_register:
            await self.__stop_registery()


__cache_key = "default"
__cache_clients: Dict[str, EurekaClient] = {}
__cache_clients_lock = RLock()


async def init_async(eureka_server: str = _DEFAULT_EUREKA_SERVER_URL,
                     eureka_domain: str = "",
                     region: str = "",
                     zone: str = "",
                     eureka_availability_zones: Dict[str, str] = {},
                     eureka_protocol: str = "http",
                     eureka_basic_auth_user: str = "",
                     eureka_basic_auth_password: str = "",
                     eureka_context: str = "/eureka",
                     prefer_same_zone: bool = True,
                     should_register: bool = True,
                     should_discover: bool = True,
                     on_error: Callable = None,
                     app_name: str = "",
                     instance_id: str = "",
                     instance_host: str = "",
                     instance_ip: str = "",
                     instance_ip_network: str = "",
                     instance_port: int = _DEFAULT_INSTNACE_PORT,
                     instance_unsecure_port_enabled: bool = True,
                     instance_secure_port: int = _DEFAULT_INSTNACE_SECURE_PORT,
                     instance_secure_port_enabled: bool = False,
                     data_center_name: str = _DEFAULT_DATA_CENTER_INFO,  # Netflix, Amazon, MyOwn
                     renewal_interval_in_secs: int = _RENEWAL_INTERVAL_IN_SECS,
                     duration_in_secs: int = _DURATION_IN_SECS,
                     home_page_url: str = "",
                     status_page_url: str = "",
                     health_check_url: str = "",
                     secure_health_check_url: str = "",
                     vip_adr: str = "",
                     secure_vip_addr: str = "",
                     is_coordinating_discovery_server: bool = False,
                     metadata: Dict = {},
                     remote_regions: List[str] = [],
                     ha_strategy: int = HA_STRATEGY_RANDOM,
                     strict_service_error_policy: bool = True) -> EurekaClient:
    """
    Initialize an EurekaClient object and put it to cache, you can use a set of functions to do the service.

    Unlike using EurekaClient class that you need to start and stop the client object by yourself, this method 
    will start the client automatically after the object created.

    read EurekaClient for more information for the parameters details.
    """
    with __cache_clients_lock:
        if __cache_key in __cache_clients:
            _logger.warn(
                "A client is already running, try to stop it and start the new one!")
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
                              prefer_same_zone=prefer_same_zone,
                              should_register=should_register,
                              should_discover=should_discover,
                              on_error=on_error,
                              app_name=app_name,
                              instance_id=instance_id,
                              instance_host=instance_host,
                              instance_ip=instance_ip,
                              instance_ip_network=instance_ip_network,
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
                              ha_strategy=ha_strategy,
                              strict_service_error_policy=strict_service_error_policy)
        __cache_clients[__cache_key] = client
        await client.start()
        return client


def get_client() -> EurekaClient:
    with __cache_clients_lock:
        if __cache_key in __cache_clients:
            return __cache_clients[__cache_key]
        else:
            return None


async def walk_nodes_async(app_name: str = "",
                           service: str = "",
                           prefer_ip: bool = False,
                           prefer_https: bool = False,
                           walker: Callable = None) -> Union[str, Dict, http_client.HttpResponse]:
    cli = get_client()
    if cli is None:
        raise Exception("Discovery Client has not initialized. ")
    res = await cli.walk_nodes(app_name=app_name, service=service,
                               prefer_ip=prefer_ip, prefer_https=prefer_https, walker=walker)
    return res


async def do_service_async(app_name: str = "", service: str = "", return_type: str = "string",
                           prefer_ip: bool = False, prefer_https: bool = False,
                           method: str = "GET", headers: Dict[str, str] = None,
                           data: Union[bytes, str, Dict] = None, timeout: float = _DEFAULT_TIME_OUT
                           ) -> Union[str, Dict, http_client.HttpResponse]:
    cli = get_client()
    if cli is None:
        raise Exception("Discovery Client has not initialized. ")
    res = await cli.do_service(app_name=app_name, service=service, return_type=return_type,
                               prefer_ip=prefer_ip, prefer_https=prefer_https,
                               method=method, headers=headers,
                               data=data, timeout=timeout)

    return res


async def stop_async() -> None:
    client = get_client()
    if client is not None:
        await client.stop()

_thread_local = threading.local()


def set_event_loop(event_loop: asyncio.AbstractEventLoop):
    if not isinstance(event_loop, asyncio.AbstractEventLoop):
        raise Exception("You must set an even loop object into this.")
    _thread_local.event_loop = event_loop


def get_event_loop() -> asyncio.AbstractEventLoop:
    if not hasattr(_thread_local, "event_loop"):
        try:
            _thread_local.event_loop = asyncio.new_event_loop()
        except:
            _thread_local.event_loop = asyncio.get_event_loop()
    return _thread_local.event_loop


def init(eureka_server: str = _DEFAULT_EUREKA_SERVER_URL,
         eureka_domain: str = "",
         region: str = "",
         zone: str = "",
         eureka_availability_zones: Dict[str, str] = {},
         eureka_protocol: str = "http",
         eureka_basic_auth_user: str = "",
         eureka_basic_auth_password: str = "",
         eureka_context: str = "/eureka",
         prefer_same_zone: bool = True,
         should_register: bool = True,
         should_discover: bool = True,
         on_error: Callable = None,
         app_name: str = "",
         instance_id: str = "",
         instance_host: str = "",
         instance_ip: str = "",
         instance_ip_network: str = "",
         instance_port: int = _DEFAULT_INSTNACE_PORT,
         instance_unsecure_port_enabled: bool = True,
         instance_secure_port: int = _DEFAULT_INSTNACE_SECURE_PORT,
         instance_secure_port_enabled: bool = False,
         data_center_name: str = _DEFAULT_DATA_CENTER_INFO,  # Netflix, Amazon, MyOwn
         renewal_interval_in_secs: int = _RENEWAL_INTERVAL_IN_SECS,
         duration_in_secs: int = _DURATION_IN_SECS,
         home_page_url: str = "",
         status_page_url: str = "",
         health_check_url: str = "",
         secure_health_check_url: str = "",
         vip_adr: str = "",
         secure_vip_addr: str = "",
         is_coordinating_discovery_server: bool = False,
         metadata: Dict = {},
         remote_regions: List[str] = [],
         ha_strategy: int = HA_STRATEGY_RANDOM,
         strict_service_error_policy: bool = True) -> EurekaClient:
    """
    Initialize an EurekaClient object and put it to cache, you can use a set of functions to do the service.

    Unlike using EurekaClient class that you need to start and stop the client object by yourself, this method 
    will start the client automatically after the object created.

    read EurekaClient for more information for the parameters details.
    """
    return get_event_loop().run_until_complete(init_async(eureka_server=eureka_server,
                                                          eureka_domain=eureka_domain,
                                                          region=region,
                                                          zone=zone,
                                                          eureka_availability_zones=eureka_availability_zones,
                                                          eureka_protocol=eureka_protocol,
                                                          eureka_basic_auth_user=eureka_basic_auth_user,
                                                          eureka_basic_auth_password=eureka_basic_auth_password,
                                                          eureka_context=eureka_context,
                                                          prefer_same_zone=prefer_same_zone,
                                                          should_register=should_register,
                                                          should_discover=should_discover,
                                                          on_error=on_error,
                                                          app_name=app_name,
                                                          instance_id=instance_id,
                                                          instance_host=instance_host,
                                                          instance_ip=instance_ip,
                                                          instance_ip_network=instance_ip_network,
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
                                                          ha_strategy=ha_strategy,
                                                          strict_service_error_policy=strict_service_error_policy))


def walk_nodes(app_name: str = "",
               service: str = "",
               prefer_ip: bool = False,
               prefer_https: bool = False,
               walker: Callable = None) -> Union[str, Dict, http_client.HttpResponse]:
    return get_event_loop().run_until_complete(walk_nodes_async(app_name=app_name, service=service,
                                                                prefer_ip=prefer_ip, prefer_https=prefer_https, walker=walker))


def do_service(app_name: str = "", service: str = "", return_type: str = "string",
               prefer_ip: bool = False, prefer_https: bool = False,
               method: str = "GET", headers: Dict[str, str] = None,
               data: Union[bytes, str, Dict] = None, timeout: float = _DEFAULT_TIME_OUT
               ) -> Union[str, Dict, http_client.HttpResponse]:

    return get_event_loop().run_until_complete(do_service_async(app_name=app_name, service=service, return_type=return_type,
                                                                prefer_ip=prefer_ip, prefer_https=prefer_https,
                                                                method=method, headers=headers,
                                                                data=data, timeout=timeout))


def stop() -> None:
    get_event_loop().run_until_complete(stop_async())
