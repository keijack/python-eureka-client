# python-eureka-client

[![PyPI version](https://badge.fury.io/py/py-eureka-client.png)](https://badge.fury.io/py/py-eureka-client)

## 描述

这是一个使用 Python 语言编写的 eureka 客户端，你可以非常简单的使得它与你的其他 Spring Cloud 组件集成在一起。

## 支持版本

Python 2.7 / 3.6+ (3.5 也应该支持，但未测试)

## 特点

* 同时支持注册以及发现服务。
* 支持故障切换。
* 支持DNS发现。
* 非常简单的配置过程，堪比 Springboot 的配置文件。
* 自动化的心跳以及组件状态机制，不需要开发者维护心跳。
* 自动化的退出机制。只要 Python 进程正常退出，组件会自己从 eureka 服务器退出。
* 封装了调用其他服务的接口，用法类似 Spring boot 的 RestTemplate。
* 调用其他服务时支持多种 HA（高可用）的策略

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
```

你也可以直接使用 `EurekaClient` 类。

```python
from py_eureka_client.eureka_client import EurekaClient
client = EurekaClient(eureka_server="http://my_eureka_server_peer_1/eureka/v2,http://my_eureka_server_peer_2/eureka/v2", app_name="python_module_1", instance_port=9090)
client.start()
res = client.do_service("OTHER-SERVICE-NAME", "/service/context/path")
print("result of other service" + res)
# when server is shutted down:
client.stop()
```

事实上，`init` 和相关的方法只是 `EurekaClient` 的一个门面（facade），其底层最终还是包含这一个 `EurekaClient` 的实例对象。你可以接收 `init` 方法的返回值，或者使用 `eureka_client.get_client()` 取得这个对象。`init` 会自动开始注册、心跳流程，并且会在程序退出的时候自动发送退出信号。而如果你 直接使用 `EurekaClient` 对象，你需要显式调用`start()` 和 `stop()` 方法来开始和停止注册过程。

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

*请注意，如果你将 python 组件和 eureka 服务器部署在一起，计算出来的 ip 会是 `127.0.0.1`，因此在这种情况下，为了保证其他组件能够访问你的组件，请必须指定`instance_host`或者`instance_ip`字段。*

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

*注意：`py-eureka-client`首先会尝试使用 `dnspython` 来解析 DNS，但是 `dnspython` 从 2.0.0 起就不再支持 python2 了，而 `py-eureka-client` 当前还是支持 `python2` 的，因此，`dnspython` 并没有引入到项目工程当中。所有，如果你使用到这项特性，请手动安装 `dnspython` 依赖库。*

*Python 3:*

```shell
python3 -m pip install dnspython
```

*python2:*

```shell
python2 -m pip install dnspython==1.16.0
```

*如果你没有安装 `dnspytho`，`py-eureka-client` 会尝试 `host` 命令来解析 DNS，`host` 命令默认在许多的 Linux 发行版本中都默认有安装。但如果是在 docker 容器的一些简化系统中，你可能需要手动安装这个命令。*

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

上述参数中，return_type 可以选择传入`json`，如果传入`json`，则该接口返回一个 `dict` 对象。该参数也可不传入，默认返回为 `str`。

这个方法还接受其他的参数，剩余的参数和 `urllib.request.urlopen`(python2 是 `urllib2.urlopen`) 接口一致。请参考相关的接口或者源代码进行传入。

这个方法还提供异步的版本：

```python
import py_eureka_client.eureka_client as eureka_client

def success_callabck(data):
    # type: (Union[str, dict]) -> object
    # 处理正常返回的参数
    print(data)

def error_callback(error):
    # type: (urllib.request.HTTPError) -> object
    # 处理错误
    print(error)

eureka_client.do_service_async("OTHER-SERVICE-NAME", "/service/context/path", on_success=success_callabck, on_error=error_callback)
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

def success_callabck(data):
    # type: (Union[str, dict]) -> object
    print(data)

def error_callback(error):
    # type: (urllib.request.HTTPError) -> object
    print(error)

eureka_client.walk_nodes("OTHER-SERVICE-NAME", "/service/context/path",
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

默认情况下，组件使用了内置的 urllib.request (python 2 中时 urllib2 ) 来进行 HTTP 请求。你可以使用别的 HTTP 库来进行访问。这在自签名的 HTTPS 证书的场景下尤为有效。

你需要以下步骤来使用自己的 HTTP 客户端：

1. 继承 `py_eureka_client.http_client` 中的 `HttpClient` 类。
2. 重写该类的 `urlopen` 方法，注意：该方法返回的是响应体的文本。
3. 将你定义的类设置到`py_eureka_client.http_client` 中。

```python
import py_eureka_client.http_client as http_client

# 1. 继承 `py_eureka_client.http_client` 中的 `HttpClient` 类。
class MyHttpClient(http_client.HttpClient):

    # 2. 重写该类的 `urlopen` 方法，注意：该方法返回的是响应体的文本。
    # 请注意，如果你要抛出异常，请确保抛出的是 urllib.error.HTTPError 或者 urllib.error.URLError
    # (Python 2 则分别是 urllib2.HTTPError 或者 urllib2.URLError) 否则可能会发生未可知之错误。
    def urlopen(self):
        # 以下是默认实现，你可以查看该类有哪一些参数。
        res = urllib2.urlopen(self.request, data=self.data, timeout=self.timeout,
                              cafile=self.cafile, capath=self.capath,
                              cadefault=self.cadefault, context=self.context)

        if res.info().get("Content-Encoding") == "gzip":
            try:
                # python2
                f = gzip.GzipFile(fileobj=StringIO(res.read()))
            except NameError:
                f = gzip.GzipFile(fileobj=res)
        else:
            f = res

        txt = f.read().decode(_DEFAULT_ENCODING)
        f.close()
        return txt

# 3. 将你定义的类设置到`py_eureka_client.http_client` 中。
http_client.set_http_client_class(MyHttpClient)
```

### 日志

默认情况下，日志会输出到控制台，你创建自己的 Logging Handler 来将日志输出到别处，例如一个滚动文件中：

```python
import simple_http_server.logger as logger
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


**其他更多的信息请查看项目注释。**
