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

### Use Both Registry And Discovery Service

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

### Only Register Your Server To Eureka Client

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

### Only Use Discovery Service

If your service does not provide services but want to use other components' service, you can only use this discovery client.

First, init the discovery client after your server starts up.

```python
import py_eureka_client.eureka_client as eureka_client

eureka_client.init_discovery_client("http://192.168.3.116:8761/eureka/, http://192.168.3.116:8762/eureka/")
```

Then, in your business code, use

```python
import py_eureka_client.eureka_client as eureka_client

res = eureka_client.do_service("OTHER-SERVICE-NAME", "/service/context/path")
print("result of other service" + res)

```

*do_service method will automatically try other nodes when one node return a HTTP error, until one success or all nodes being tried.*

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
