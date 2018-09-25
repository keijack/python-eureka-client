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

### Rister your python REST server to eureka server

```python
import py_eureka_client.eureka_client as eureka_client

your_rest_server_port = 9090
# The flowing code will register your server to eureka server and also start to send heartbeat every 30 seconds
eureka_client.init_registry_client(registry_server="http://your-eureka-server-peer1,http://your-eureka-server-peer2",
                                app_name="your_app_name",
                                instance_port=your_rest_server_port)

```

*If you do not specify your host and ip just like the example above, the client will choose one that could connect to eureka server.*

### Discover other service from eureka server

First, init the discovery client after your server starts up.

```python
import py_eureka_client.eureka_client as eureka_client

eureka_client.init_discovery_client("http://192.168.3.116:8761/eureka/, http://192.168.3.116:8762/eureka/")
```

Then, in your business code, use

```python
import py_eureka_client.eureka_client as eureka_client

cli = eureka_client.get_discovery_client()
res = cli.do_service("OTHER-SERVICE-NAME", "/service/context/path")
print("result of other service" + res)

```

*do_service method will automatically try other nodes when one node return a HTTP error, until one success or all nodes being tried.*

There are several HA strategies when using discovery client. You can specify it in `init_discovery_client`. They are:

* HA_STRATEGY_RANDOM, default strategy, find an node randamly.
* HA_STRATEGY_STICK, use one node until it going down.
* HA_STRATEGY_OTHER, always use a different node from the last time.
