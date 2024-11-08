# python-eureka-client

[![PyPI version](https://badge.fury.io/py/py-eureka-client.png)](https://badge.fury.io/py/py-eureka-client)

## 描述

这是一个使用 Python 语言编写的 eureka 客户端，你可以非常简单的使得它与你的其他 Spring Cloud 组件集成在一起。

## 支持版本

Python 3.7+

*从`0.9.0`开始，不再支持 python 2，如果你需要使用 python 2，请使用 `0.8.12` 版本。*

## 特点

* 同时支持注册以及发现服务。
* 支持故障切换。
* 支持DNS发现。
* 非常简单的配置过程，堪比 Springboot 的配置文件。
* 自动化的心跳以及组件状态机制，不需要开发者维护心跳。
* 封装了调用其他服务的接口，用法类似 Spring boot 的 RestTemplate。
* 调用其他服务时支持多种 HA（高可用）的策略。
* 支持普通接口调用以及异步 `async def` 接口调用。
* 底层使用的 http client 非常容易便可替换。

## 如何使用

### 安装

```Shell
pip install py_eureka_client
```

### 推荐使用

最简单的使用方法如下：

```python
import py_eureka_client.eureka_client as eureka_client

your_rest_server_host = "192.168.10.106"
your_rest_server_port = 9090
# The flowing code will register your server to eureka server and also start to send heartbeat every 30 seconds
eureka_client.init(eureka_server="http://your-eureka-server-peer1,http://your-eureka-server-peer2",
                   app_name="your_app_name",
                   # 当前组件的主机名，可选参数，如果不填写会自动计算一个，如果服务和 eureka 服务器部署在同一台机器，请必须填写，否则会计算出 127.0.0.1
                   instance_host=your_rest_server_host,
                   instance_port=your_rest_server_port,
                   # 调用其他服务时的高可用策略，可选，默认为随机
                   ha_strategy=eureka_client.HA_STRATEGY_RANDOM)
```

在你的业务代码中，通过以下的方法调用其他组件的服务

```python
import py_eureka_client.eureka_client as eureka_client

res = eureka_client.do_service("OTHER-SERVICE-NAME", "/service/context/path",
                               # 返回类型，默认为 `string`，可以传入 `json`，如果传入值是 `json`，那么该方法会返回一个 `dict` 对象
                               return_type="string")
print("result of other service" + res)
# 服务停止时调用，会调用 eureka 的 cancel 方法
eureka_client.stop()
```

你也可以直接使用 `EurekaClient` 类。

```python
from py_eureka_client.eureka_client import EurekaClient
client = EurekaClient(eureka_server="http://my_eureka_server_peer_1/eureka/v2,http://my_eureka_server_peer_2/eureka/v2", app_name="python_module_1", instance_port=9090)
await client.start()
res = await client.do_service("OTHER-SERVICE-NAME", "/service/context/path")
print("result of other service" + res)
# when server is shutted down:
await client.stop()
```

事实上，`init` 和相关的方法只是 `EurekaClient` 的一个门面（facade），其底层最终还是包含这一个 `EurekaClient` 的实例对象。你可以接收 `init` 方法的返回值，或者使用 `eureka_client.get_client()` 取得这个对象。`init` 会自动开始注册、心跳流程。而如果你 直接使用 `EurekaClient` 对象，你需要显式调用`start()` 和 `stop()` 方法来开始和停止注册过程。

从`0.11.0`开始，`EurekaClient` 提供的方法均为`async def`，而门面方面也提供对应的`async def` 版本，分别命名为 `init_async`、`do_service_async`、`walk_nodes_async`、`stop_async`。

*在接下来的文档中，我会仅使用门面（facade）函数作为例子，事实上，你可以从 `EurekaClient` 类中找到这些函数对应的方法。*

### 注册服务

最常用的注册方法是：

```Python
import py_eureka_client.eureka_client as eureka_client

eureka_server_list = "http://your-eureka-server-peer1,http://your-eureka-server-peer2"
your_rest_server_host = "http://192.168.10.11"
your_rest_server_port = 9090
# The flowing code will register your server to eureka server and also start to send heartbeat every 30 seconds
eureka_client.init(eureka_server=eureka_server_list,
                                app_name="your_app_name",
                                instance_host=your_rest_server_host,
                                instance_port=your_rest_server_port)
```

你还可以不传入`instance_host`参数，如果不传入那个参数，组件会根据当前的网络取得一个 ip 作为参数。

```Python
import py_eureka_client.eureka_client as eureka_client

your_rest_server_port = 9090
# The flowing code will register your server to eureka server and also start to send heartbeat every 30 seconds
eureka_client.init(eureka_server="http://your-eureka-server-peer1,http://your-eureka-server-peer2",
                                app_name="your_app_name",
                                instance_port=your_rest_server_port)
```

如果你有多个 `zone`，你可以通过参数 `eureka_availability_zones` 来进行配置。

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

但如果你希望更具灵活性，你可以使用 DNS 来配置 Eureka 服务器的 URL。

假设，你有以下的 DNS txt 记录：

```
txt.us-east-1.mydomaintest.netflix.net="us-east-1c.mydomaintest.netflix.net" "us-east-1d.mydomaintest.netflix.net" "us-east-1e.mydomaintest.netflix.net"
```

然后，你可以使用 DNS txt 记录 为每个上述的 `zone` 定义实际的 Eureka 服务的 URL：

```
txt.us-east-1c.mydomaintest.netflix.net="ec2-552-627-568-165.compute-1.amazonaws.com" "ec2-368-101-182-134.compute-1.amazonaws.com"
txt.us-east-1d.mydomaintest.netflix.net="ec2-552-627-568-170.compute-1.amazonaws.com"
txt.us-east-1e.mydomaintest.netflix.net="ec2-500-179-285-592.compute-1.amazonaws.com"
```

之后，你可以通过这样的方式来初始化 eureka client：

```python
import py_eureka_client.eureka_client as eureka_client
eureka_client.init(eureka_domain="mydomaintest.netflix.net",
                region="us-east-1",
                zone="us-east-1c",
                app_name="python_module_1", 
                instance_port=9090,
                data_center_name="Amazon")
```

你可以独立配置 eureka 服务器的协议、简单认证、上下文路径，而不把这些放在 URL中。

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

或者

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

*关于默认的 `instance_ip` 和 `instance_host`*：

如 Spring 的实现一样，`py-eureka-client` 在亚马逊的数据中心，会使用数据中心元数据服务取得的 `local-ipv4` 和 `local-hostname` 做为默认值，否则则会取第一个取得的具有 IPv4 的地址的网卡地址作为默认的地址。

你的机器环境中可能存在多个网卡（特别是使用 docker 容器的时候），那么你可以使用 `instance_ip_network` 参数指定网段来取得 IP 地址：

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

如果你仅想动态取得 IP，但需要手动指定 host，那么你可以使用以下方法来实习：

```python
import py_eureka_client.netint_utils as netint_utils

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

### 错误回调

你可以在初始化时指定一个错误回调函数，当`注册`、`发现`、`状态更新`时，如果发生错误，这个回调函数会被触发。请注意，如果你传入多个 eureka 服务器的 url，那么该回调会在所有服务器均尝试失败之后才会被触发。

定义的回调函数必须接收两个变量：一个是错误类型，一个是异常本身，请参考：

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

### 调用远程服务

当初始化完 eureka client 之后，你就可以通过拉取 eureka server 的信息来调用远程服务了。

最简单的调用方式是：

```python
import py_eureka_client.eureka_client as eureka_client

try:
    res = eureka_client.do_service("OTHER-SERVICE-NAME", "/service/context/path", return_type="string")
    print("result of other service" + res)
except urllib.request.HTTPError as e:
    # If all nodes are down, a `HTTPError` will raise.
    print(e)
```

上述参数中，return_type 可以选择传入`json`，如果传入`json`，则该接口返回一个 `dict` 对象，如果传入`response_object`，那么该方法会返回原始的 HTTPResponse 对象。该参数也可不传入，默认返回的为 `str` 的响应体的内容。

这个方法还提供异步的版本：

```python
import py_eureka_client.eureka_client as eureka_client

res = await eureka_client.do_service_async("OTHER-SERVICE-NAME", "/service/context/path")
```

如果你不希望使用内置的 HTTP 客户端，希望使用其他的客户端的话，你可以使用 `walk_nodes` 函数来实现：

```python
import py_eureka_client.eureka_client as eureka_client

def walk_using_your_own_urllib(url):
    print(url)
    """
    # 根据传入的 url 参数，通过你选择的其他库来调用其他组件提供的 Restful 接口。
    # 你返回的数据会直接被 `eureka_client.walk_nodes` 函数返回
    # 如果你发现给定的 url 的节点无法访问，请 raise 一个 `urllib.request.HTTPError`(urllib2.HTTPError in python2)，
    # 之后 `eureka_client.walk_nodes` 会继续寻找其他状态为 UP 的节点来调用。
    """

try:
    # `res` 是你在 walk_using_your_own_urllib 中返回的数据。
    res = eureka_client.walk_nodes("OTHER-SERVICE-NAME", "/service/context/path", walker=walk_using_your_own_urllib)
    print(res)
except urllib.request.HTTPError as e:
    # 如果所有的节点没有正确返回结果，以上错误将被抛出
    print(e)
```

这个方法同样有一个异步的版本：

```python
import py_eureka_client.eureka_client as eureka_client

def walk_using_your_own_urllib(url):
    print(url)


res = await eureka_client.walk_nodes("OTHER-SERVICE-NAME", "/service/context/path",
                          walker=walk_using_your_own_urllib,
                          on_success=success_callabck,
                          on_error=error_callback)
```

### 高可用

`do_service` 和 `walk_nodes` 方法支持 HA（高可用），该方法会尝试所有从 ereka 服务器取得的节点，直至其中一个节点返回数据，或者所有的节点都尝试失败。

该方法有几种 HA 的策略，这些策略分别是：

* HA_STRATEGY_RANDOM, 默认策略，随机取得一个节点。
* HA_STRATEGY_STICK, 随机取得一个节点之后一直使用该节点，直至这个节点被删除或者状态设为 DOWN。
* HA_STRATEGY_OTHER, 总是使用和上次不同的节点。

如果你需要修改这些策略，你可以初始化发现服务时指定相应的策略：

```python
import py_eureka_client.eureka_client as eureka_client

eureka_server_list = "http://your-eureka-server-peer1,http://your-eureka-server-peer2"

eureka_client.init(eureka_server=eureka_server_list,
                   app_name="your_app_name",
                   instance_port=9090,
                   ha_strategy=eureka_client.HA_STRATEGY_OTHER)
```

如果上述内置的 HA 策略都不能满足你的需求，你可以将按以下的办法取得整个服务注册库来构建你自己的访问方法：

```python
import py_eureka_client.eureka_client as eureka_client

client = eureka_client.get_client()
app = client.applications.get_application("OTHER-SERVICE-NAME")
up_instances = app.up_instances
up_instances_same_zone = app.up_instances_in_zone(client.zone)
up_instances_other_zone = app.up_instances_not_in_zone(client.zone)
inst = up_instances[0]

# ... 组装访问链接和进行远程调用

```

### 使用三方 HTTP 客户端

默认情况下，组件使用了内置的 urllib.request 来进行 HTTP 请求。你可以使用别的 HTTP 库来进行访问。这在自签名的 HTTPS 证书的场景下尤为有效。

从 `0.11.0` 开始，底层的 Httplient 类的所有方法都定义为 `async def`，这使得你更容易地接入一些异步 IO 的第三方库，例如 `aiohttp`。

你需要以下步骤来使用自己的 HTTP 客户端：

1. （可选）大部分情况下，你需要编写一个继承`py_eureka_client.http_client.HttpResponse`的类，该类必须提供两个属性`raw_response`和`body_text`。其中，`raw_response`仅在`do_service`传入`response_object`时返回。
2. 编写一个类继承 `py_eureka_client.http_client.HttpClient` 类。
3. 重写该类的 `urlopen` 方法，该方法需要返回一个`py_eureka_client.http_client.HttpResponse`的子类对象。
4. 将你定义的类的对象设置到`py_eureka_client.http_client` 中。

```python
import py_eureka_client.http_client as http_client

# 1. 编写一个继承`py_eureka_client.http_client.HttpResponse`的类，该类必须提供两个属性`raw_response`和`body_text`。
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

# 2. 编写一个类继承 `py_eureka_client.http_client.HttpClient` 类
class MyHttpClient(http_client.HttpClient):

    # 3. 重写该类的 `urlopen` 方法，该方法需要返回一个`py_eureka_client.http_client.HttpResponse`的子类对象
    # 如果你需要返回异常，请注意返回 `http_client.HTTPError` 或者 `http_client.URLError`。
    async def urlopen(self, request: Union[str, http_client.HttpRequest] = None,
                      data: bytes = None, timeout: float = None) -> http_client.HttpResponse:
        res = await your_own_http_client_lib.do_the_visit(request, data, timeout)
        # 返回你定义的 HttpRespone 对象。
        return MyHttpResponse(res)
        # 你也可以在此解析了 body_text，摄入 HttpResponse 中，那么你就不需要继承 http_client.HttpResponse 了。
        # body_txt = parse_res_body(res)
        # http_res = http_client.HttpResponse()
        # http_res.raw_response = res
        # http_res.body_text = body_text
        # return http_res
            

# 4. 将你的类对象设置到 http_client 中。
http_client.set_http_client(MyHttpClient())
```

### 日志

默认情况下，日志会输出到控制台，你创建自己的 Logging Handler 来将日志输出到别处，例如一个滚动文件中：

```python
import py_eureka_client.logger as logger
import logging

_formatter = logging.Formatter(fmt='[%(asctime)s]-[%(name)s]-%(levelname)-4s: %(message)s')
_handler = logging.TimedRotatingFileHandler("/var/log/py-eureka-client.log", when="midnight", backupCount=7)
_handler.setFormatter(_formatter)
_handler.setLevel("INFO")

logger.set_handler(_handler)
```

如果你想增加一个日志控制器而不是想替代内置的，那么你可以使用以下方法：

```python
logger.add_handler(_handler)
```

你也可以使用以下方法来设置日志输出级别：

```python
logger.set_level("DEBUG")
```

这个日志使用了一个背景线程来输出日志，因此其非常适合使用在多线程的场景，特别你是你有多个 logger 共用一个 `TimedRotatingFileHandler` 的时候。在多线程的场景下，这个日志控制器经常不能正常地按时切割文件。

### 自定义 Logger

你可以通过以下方法来设置自己的 logger：

```python
import py_eureka_client.logger as logger

logger.set_custom_logger(your_logger)
```

## 亚马逊数据中心支持

理论上，这个组件可以正常运行在亚马逊的数据中心。当运行在亚马逊数据中心，会从亚马逊的 metadata 服务中取得相关的元数据并且自动填充到 DataCenterInfo 中，填充的字段信息来源自 Netflix 的 Java 客户端中的 `com.netflix.appinfo.AmazonInfo` 类。**不过**，由于我本人没有亚马逊的相关环境作为测试，所以，在实际的运行当中，可能会发生错误。如果真的发生了错误的话，请提出 ISSUE 并且提供详细的日志，我会尽力支持。如果运行没有问题，如果可以，也欢迎在这个[问题](https://github.com/keijack/python-eureka-client/issues/33)进行回复。


## 更多信息

**其他更多的信息请查看项目注释。**
