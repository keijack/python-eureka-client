# python-eureka-client

## Discription

This is an eureka client written in python, you can easily intergrate your python components with spring cloud.

## Support Python Version

Python 2.7 / 3.6+ (It should also work at 3.5, not test)

## Why choose

* Register your python components to eureka server.
* Support multiple eureka server registration.
* Send heartbeat to eureka server.
* Auto unregister from eureka server when your server down.
* Discovery apps from eureka server.
* Easy to use interface to use other REST service.
* Auto try other nodes when one nodes down.

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

*More information about discovery client, please read `Use Discovery Client` Chapter*

### Use Registry Client Only

If your server only provide service, and does not need other components' service, you can only register your client to Eureka server and ignore the discovery client. Code is below:

```Python
import py_eureka_client.eureka_client as eureka_client

your_rest_server_port = 9090
# The flowing code will register your server to eureka server and also start to send heartbeat every 30 seconds
eureka_client.init_registry_client(eureka_server="http://your-eureka-server-peer1,http://your-eureka-server-peer2",
                                app_name="your_app_name",
                                instance_port=your_rest_server_port)
```

*If you do not specify your host and ip just like the example above, the client will choose one that could connect to eureka server.*

### Use Discovery Service

If your service does not provide services but want to use other components' service, you can only use this discovery client.

First, init the discovery client after your server starts up.

```python
import py_eureka_client.eureka_client as eureka_client

eureka_client.init_discovery_client("http://192.168.3.116:8761/eureka/, http://192.168.3.116:8762/eureka/")
```

No mather you ust `init` or `init_discovery_client`, then you can now use the following methods to use other components' service:

This is the most simplist way to do service:

```python
import py_eureka_client.eureka_client as eureka_client

try:
    res = eureka_client.do_service("OTHER-SERVICE-NAME", "/service/context/path")
    print("result of other service" + res)
except urllib.request.HTTPError as e:
    # If all nodes are down, a `HTTPError` will raise.
    print(e)
```

`do_service` function also recieve a `return_type` keyword parameter, which when "json" was passed, the result will be a `dict` type object. And other parameters are follow the `urllib.request.urlopen` (`urllib2.urlopen` in python2) method, including `data`, etc. Please read the relative document for more information.

You can also use its `async` version:

```python
import py_eureka_client.eureka_client as eureka_client

def success_callabck(data):
    # type: (Union[str, dict]) -> object
    # do what you will use of the result.
    print(data)

def error_callback(error):
    # type: (urllib.request.HTTPError) -> object
    # do what you need to do when error occures
    print(error)

eureka_client.do_service_async("OTHER-SERVICE-NAME", "/service/context/path", on_success=success_callabck, on_error=error_callback)
```

*do_service method will automatically try other nodes when one node return a HTTP error, until one success or all nodes being tried.*

If you want to use your own http library to do the request, use `walk_nodes` function:

```python
import py_eureka_client.eureka_client as eureka_client

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

def success_callabck(data):
    # type: (Union[str, dict]) -> object
    # do what you will use of the result.
    print(data)

def error_callback(error):
    # type: (urllib.request.HTTPError) -> object
    # do what you need to do when error occures
    print(error)

eureka_client.walk_nodes("OTHER-SERVICE-NAME", "/service/context/path",
                          walker=walk_using_your_own_urllib,
                          on_success=success_callabck,
                          on_error=error_callback)
```

### High Available Strategies

There are several HA strategies when using discovery client. They are:

* HA_STRATEGY_RANDOM, default strategy, find an node randamly.
* HA_STRATEGY_STICK, use one node until it going down.
* HA_STRATEGY_OTHER, always use a different node from the last time.

In your `init` function or `init_discovery_client`, you can specify one of the above strategies:

```python
import py_eureka_client.eureka_client as eureka_client
# General init method
eureka_client.init(eureka_server="http://your-eureka-server-peer1,http://your-eureka-server-peer2",
                   app_name="your_app_name",
                   instance_port=your_rest_server_port,
                   ha_ha_strategy=eureka_client.HA_STRATEGY_STICK)

# If you only use the discovery client
eureka_client.init_discovery_client("http://192.168.3.116:8761/eureka/, http://192.168.3.116:8762/eureka/",
                                    ha_ha_strategy=eureka_client.HA_STRATEGY_STICK)
```

### Stop Client

This module will stop and unregister from eureka server automatically when your program exit normally. (use `@atexit`), however, if you want to stop it by yourself, please use the following code:

```python
import py_eureka_client.eureka_client as eureka_client

eureka_client.stop()
```