# python-eureka-client

[![PyPI version](https://badge.fury.io/py/py-eureka-client.png)](https://badge.fury.io/py/py-eureka-client)

## Discription

This is an eureka client written in python, you can easily intergrate your python components with spring cloud.

## Support Python Version

Python 3.7+

*From `0.9.0`, python 2 is no longer supported, if you are using python 2, please use  version `0.8.12`.*

## Why choose

* Register your python components to eureka server.
* Support failover.
* Support DNS discovery. 
* Send heartbeat to eureka server.
* Pull registry from eureka server.
* Easy to use interface to use other REST service.
* HA when calling other REST service.
* Both trandictional and async def interfaces are provided.
* The http client lib is replacable.

## How to use

### Install

```Shell
pip install py_eureka_client
```

### Getting Start

This is the easiest way to use this component.

```python
import py_eureka_client.eureka_client as eureka_client

your_rest_server_port = 9090
# The flowing code will register your server to eureka server and also start to send heartbeat every 30 seconds
eureka_client.init(eureka_server="http://your-eureka-server-peer1,http://your-eureka-server-peer2",
                   app_name="your_app_name",
                   instance_port=your_rest_server_port)
```

Then, in your business code, use

```python
import py_eureka_client.eureka_client as eureka_client

res = eureka_client.do_service("OTHER-SERVICE-NAME", "/service/context/path")
print("result of other service" + res)

```

You can also use the `EurekaClient` class. 

```python
from py_eureka_client.eureka_client import EurekaClient
client = EurekaClient(eureka_server="http://my_eureka_server_peer_1/eureka/v2,http://my_eureka_server_peer_2/eureka/v2", app_name="python_module_1", instance_port=9090)
await client.start()
res = await client.do_service("OTHER-SERVICE-NAME", "/service/context/path")
print("result of other service" + res)
# when server is shutted down:
await client.stop()
```

In fact, the `init` function is a facade of the EurekaClient, it holds a client object behind, you can get that by catching its return value or use `eureka_client.get_client()` to get it. The `init` function will automatically start the client, while using raw `EurekaClient`, you must call the `start()` and `stop()` method explicitly. 


From `0.11.0`, all the methods in `EurekaClient` are defined `async`, and there are also async facade for `init`, `do_servise`, `stop` functions names `init_async`, `do_service_async`, `sto_async`.

### Registering to Eureka Server

The most common method to will be like:

```Python
import py_eureka_client.eureka_client as eureka_client

your_rest_server_port = 9090
eureka_client.init(eureka_server="http://your-eureka-server-peer1,http://your-eureka-server-peer2",
                                app_name="python_module_1",
                                instance_port=your_rest_server_port)
```

But if you have deploy your eureka server in several zones, you should specify the `eureka_availability_zones` parameter.

```python
import py_eureka_client.eureka_client as eureka_client
eureka_client.init(eureka_availability_zones={
                "us-east-1c": "http://ec2-552-627-568-165.compute-1.amazonaws.com:7001/eureka/v2/,http://ec2-368-101-182-134.compute-1.amazonaws.com:7001/eureka/v2/",
                "us-east-1d": "http://ec2-552-627-568-170.compute-1.amazonaws.com:7001/eureka/v2/",
                "us-east-1e": "http://ec2-500-179-285-592.compute-1.amazonaws.com:7001/eureka/v2/"}, 
                zone="us-east-1c",
                app_name="python_module_1", 
                instance_port=9090,
                data_center_name="Amazon")
```

If you are looking for flexibility, you should configure Eureka service URLs using DNS.

For instance, following is a DNS TXT record created in the DNS server that lists the set of available DNS names for a zone.

```
txt.us-east-1.mydomaintest.netflix.net="us-east-1c.mydomaintest.netflix.net" "us-east-1d.mydomaintest.netflix.net" "us-east-1e.mydomaintest.netflix.net"
```

Then, you can define TXT records recursively for each zone similar to the following (if more than one hostname per zone, space delimit)

```
txt.us-east-1c.mydomaintest.netflix.net="ec2-552-627-568-165.compute-1.amazonaws.com" "ec2-368-101-182-134.compute-1.amazonaws.com"
txt.us-east-1d.mydomaintest.netflix.net="ec2-552-627-568-170.compute-1.amazonaws.com"
txt.us-east-1e.mydomaintest.netflix.net="ec2-500-179-285-592.compute-1.amazonaws.com"
```

And then you can create the client like: 

```python
import py_eureka_client.eureka_client as eureka_client
eureka_client.init(eureka_domain="mydomaintest.netflix.net",
                region="us-east-1",
                zone="us-east-1c",
                app_name="python_module_1", 
                instance_port=9090,
                data_center_name="Amazon")
```

You can specify the protocol, basic authentication and context path of your eureka server separatly rather than setting it at the URL. 

```python
import py_eureka_client.eureka_client as eureka_client
eureka_client.init(eureka_domain="mydomaintest.netflix.net",
                region="us-east-1",
                zone="us-east-1c",
                eureka_protocol="https",
                eureka_basic_auth_user="keijack",
                eureka_basic_auth_password="kjauthpass",
                eureka_context="/eureka/v2",
                app_name="python_module_1", 
                instance_port=9090,
```

or

```python
import py_eureka_client.eureka_client as eureka_client
eureka_client.init(eureka_server="your-eureka-server-peer1,your-eureka-server-peer2",
                eureka_protocol="https",
                eureka_basic_auth_user="keijack",
                eureka_basic_auth_password="kjauthpass",
                eureka_context="/eureka/v2",
                app_name="python_module_1", 
                instance_port=9090)
```

*About the instance `IP` and `hostname`*:

If you are using a `Amazon` data center, `py-eureka-client` will try to use `local-ipv4` and `local-hostname` get from Amazon metadata service. In other cases, `py-eureka-client` will use the first non-loopback ip address and hostname from your net interface. 

You can also specify both these tow field or just one of them explicitly:

```python
eureka_client.init(eureka_server="your-eureka-server-peer1,your-eureka-server-peer2",
                eureka_protocol="https",
                eureka_basic_auth_user="keijack",
                eureka_basic_auth_password="kjauthpass",
                eureka_context="/eureka/v2",
                app_name="python_module_1", 
                instance_ip="192.168.10.168",
                instance_host="my-py-component.mydomian.com",
                instance_port=9090)
```

In some case you might have more than one interfaces attached, for example, you are running your application in a docker-container. In this case you can specify a network via `instance_ip_network` to be used to get the container's ip and host. You can use:

```python
eureka_client.init(eureka_server="your-eureka-server-peer1,your-eureka-server-peer2",
                eureka_protocol="https",
                eureka_basic_auth_user="keijack",
                eureka_basic_auth_password="kjauthpass",
                eureka_context="/eureka/v2",
                app_name="python_module_1", 
                instance_ip_network="192.168.10.0/24",
                instance_port=9090)
```

If you want to get the ip only and sepecify the host by yourself, try:

```python
import py_eureka_client.netint_utils as netint_utils

# you can get the ip only
ip = netint_utils.get_first_non_loopback_ip("192.168.10.0/24")
host = "my-py-component.mydomian.com"

eureka_client.init(eureka_server="your-eureka-server-peer1,your-eureka-server-peer2",
                eureka_protocol="https",
                eureka_basic_auth_user="keijack",
                eureka_basic_auth_password="kjauthpass",
                eureka_context="/eureka/v2",
                app_name="python_module_1", 
                instance_ip=ip,
                instance_host=host,
                instance_port=9090)
```

### Error Callback

You can specify a callback function when initializing the eureka client, when errors occur in `register`, `discover` or `status update` phase, the callback function will be called to inform you. The callback function will be called only when all the eureka server url are all tried and fails. 

The callback function should accept 2 arguments. which are the error type and the exception itself. please check:

```python
def on_err(err_type: str, err: Exception):
    if err_type in (eureka_client.ERROR_REGISTER, eureka_client.ERROR_DISCOVER):
        eureka_client.stop()
    else:
        print(f"{err_type}::{err}")

your_rest_server_port = 9090
eureka_client.init(eureka_server="http://your-eureka-server-peer1,http://your-eureka-server-peer2",
                                app_name="python_module_1",
                                instance_port=your_rest_server_port,
                                on_error=on_err)

```

### Call Remote Service

After `init` the eureka client, this is the most simplist way to do service:

```python
import py_eureka_client.eureka_client as eureka_client

try:
    res = eureka_client.do_service("OTHER-SERVICE-NAME", "/service/context/path")
    print("result of other service" + res)
except urllib.request.HTTPError as e:
    # If all nodes are down, a `HTTPError` will raise.
    print(e)
```

`do_service` function also recieve a `return_type` keyword parameter, which when `json` was passed, the result will be a `dict` type object whereas `response_object` is pass, the original HTTPResponse object will be return. Please read the relative document for more information.

You can also use its `async` version:

```python
import py_eureka_client.eureka_client as eureka_client

res = await eureka_client.do_service_async("OTHER-SERVICE-NAME", "/service/context/path")
```

*do_service method will automatically try other nodes when one node return a HTTP error, until one success or all nodes being tried.*

If you want to handle all the services' calling, you can use `walk_nodes` function:

```python
import py_eureka_client.eureka_client as eureka_client

# you can define this function with `async def`
def walk_using_your_own_urllib(url):
    print(url)
    """
    # Connect to url and read result, then return it.
    # The result you return here will be returned to the `eureka_client.walk_nodes` function
    # If you want find this node is down, you can raise a `urllib.request.HTTPError`(urllib2.HTTPError in python2)
    # Then the `eureka_client.walk_nodes` will try to find another node to do the service.
    """

# result is the result that you return in walk_using_your_own_urllib function
try:
    res = eureka_client.walk_nodes("OTHER-SERVICE-NAME", "/service/context/path", walker=walk_using_your_own_urllib)
    print(res)
except urllib.request.HTTPError as e:
    # If all nodes are down, a `HTTPError` will raise.
    print(e)
```

A `async` version is also provied:

```python
import py_eureka_client.eureka_client as eureka_client

def walk_using_your_own_urllib(url):
    print(url)
    """
    # Connect to url and read result, then return it.
    # The result you return here will be returned to the `eureka_client.walk_nodes` function
    # If provided node is down, you can raise a `urllib.request.HTTPError`(urllib2.HTTPError in python2)
    # Then the `eureka_client.walk_nodes` will try to find another node to do the service.
    """

res = await eureka_client.walk_nodes_async("OTHER-SERVICE-NAME", "/service/context/path",
                          walker=walk_using_your_own_urllib)
```

### High Available Strategies

There are several HA strategies when using discovery client. They are:

* HA_STRATEGY_RANDOM, default strategy, find an node randamly.
* HA_STRATEGY_STICK, use one node until it goes down.
* HA_STRATEGY_OTHER, always use a different node from the last time.

In your `init` function, you can specify one of the above strategies:

```python
import py_eureka_client.eureka_client as eureka_client
# General init method
eureka_client.init(eureka_server="http://your-eureka-server-peer1,http://your-eureka-server-peer2",
                   app_name="your_app_name",
                   instance_port=your_rest_server_port,
                   ha_strategy=eureka_client.HA_STRATEGY_STICK)
```

If the build-in stratergies do not satify you, you can load all the registry by following code:

```python
import py_eureka_client.eureka_client as eureka_client

client = eureka_client.get_client()
app = client.applications.get_application("OTHER-SERVICE-NAME")
up_instances = app.up_instances
up_instances_same_zone = app.up_instances_in_zone(client.zone)
up_instances_other_zone = app.up_instances_not_in_zone(client.zone)
inst = up_instances[0]

# ... construct your url and do the service call

```

### Use Other Http Client

You can use other http client to connect to eureka server and other service rather than the build-in urlopen method. It should be useful if you use https connections via self-signed cetificates. 

From `0.11.0`, the methods of the `http_client.HttpClient` are defined `async`, you can now use some async http libs like `aiohttp`

To do this, you should:

1. (Optional) At most scenario, you should also write a class that inherited from `py_eureka_client.http_client.HttpResponse`, for the reason of the `py_eureka_client.http_client.HttpResponse` class wraps the `http.client.HTTPResponse` which may not return by the third http libs. 
2. Write a class inherited the `HttpClient` class in `py_eureka_client.http_client`.
3. Rewrite the `urlopen` method in your class. this method must return an subclass of `py_eureka_client.http_client.HttpResponse`, which is a wrapper class that hold to properties called `raw_response` and `body_text`. 
4. Set you own HttpClient object into `py_eureka_client.http_client` by `py_eureka_client.set_http_client`

```python
import py_eureka_client.http_client as http_client

# 1. A class inherited `py_eureka_client.http_client.HttpResonse`

class MyHttpResponse(http_client.HttpResponse):

    def __init__(self, raw_response):
        """
        " This raw response will return when you pass `response_object` in the `do_service` function.
        """
        self.raw_response = raw_response
    
    @property
    def body_text(self):
        txt = ""
        """
        " Read the body text from `self.raw_response`
        """
        return txt

# 2. A class inherited `py_eureka_client.http_client.HttpClient`.
class MyHttpClient(http_client.HttpClient):

    # 3. Rewrite the `urlopen` method in your class.
    # If you want to raise an exception, please make sure that the exception is an `http_client.HTTPError` or `http_client.URLError`.     
    async def urlopen(self, request: Union[str, http_client.HttpRequest] = None,
                      data: bytes = None, timeout: float = None) -> http_client.HttpResponse:
        res = await your_own_http_client_lib.do_the_visit(request, data, timeout)
        return MyHttpResponse(res)
        # You can parse your response object here, and set the body_text to http_client.HttpResponse, then you may ignore the http_client.HttpResponse inheritance.
        # body_txt = parse_res_body(res)
        # http_res = http_client.HttpResponse()
        # http_res.raw_response = res
        # http_res.body_text = body_text
        # return http_res
            

# 4. Set your class to `py_eureka_client.http_client`. 
http_client.set_http_client(MyHttpClient())
```

### Logger

The default logger is try to write logs to the screen, you can specify the logger handler to write it to a file.

```python
import py_eureka_client.logger as logger
import logging

_formatter = logging.Formatter(fmt='[%(asctime)s]-[%(name)s]-%(levelname)-4s: %(message)s')
_handler = logging.TimedRotatingFileHandler("/var/log/py-eureka-client.log", when="midnight", backupCount=7)
_handler.setFormatter(_formatter)
_handler.setLevel("INFO")

logger.set_handler(_handler)
```

If you want to add a handler rather than replace the inner one, you can use:

```python
logger.add_handler(_handler)
```

If you want to change the logger level:

```python
logger.set_level("DEBUG")
```

This logger will first save all the log record to a global queue, and then output them in a background thread, so it is very suitable for getting several logger with a same handler, especialy the `TimedRotatingFileHandler` which may slice the log files not quite well in a mutiple thread environment. 

## Amazon Data Center Support

This component should support deploying in Amazone EC2, it should automatically load metadata from Amazon metadata service. All the metadata keys come from `com.netflix.appinfo.AmazonInfo` in Netflix's java client. BUT for the reason that I have no amazon environment to test, it may not work. If errors occurs, please submit an issue and provide some detail logs, I will try to fix it as far as I can. If it works, a reply in this [issue](https://github.com/keijack/python-eureka-client/issues/33) is wellcomed.

## More Infomation

You can find more information in the project comments.

