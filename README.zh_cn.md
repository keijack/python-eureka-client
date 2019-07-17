# python-eureka-client

## 描述

这是一个使用 Python 语言编写的 eureka 客户端，你可以非常简单的使得它与你的其他 Spring Cloud 组件集成在一起。

## 支持版本

Python 2.7 / 3.6+ (3.5 也应该支持，但未测试)

## 特点

* 同时支持注册以及发现服务。
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

通过以下代码，你可以同时使用注册以及发现服务：

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

*上述接口还支持更多的参数，请参考源代码，这个参数的大部分`Instance`对象的参数，参考以下`仅注册服务`的相关说明。*

*`ha_stratergy`参数中所需要的更多策略请参考以下`仅发现服务`的相关说明。*

在你的业务代码中，通过以下的方法调用其他组件的服务

```python
import py_eureka_client.eureka_client as eureka_client

res = eureka_client.do_service("OTHER-SERVICE-NAME", "/service/context/path",
                               # 返回类型，默认为 `string`，可以传入 `json`，如果传入值是 `json`，那么该方法会返回一个 `dict` 对象
                               return_type="string")
print("result of other service" + res)
```

*更多使用发现服务的方法，请参照`使用发现服务`章节。*

### 仅注册服务

如果你的组件仅提供服务，不需要发现其他的组件，那么你可以仅将你的组件注册到 eureka 服务中而无需初始化发现服务。

```Python
import py_eureka_client.eureka_client as eureka_client

eureka_server_list = "http://your-eureka-server-peer1,http://your-eureka-server-peer2"
your_rest_server_host = "http://192.168.10.11"
your_rest_server_port = 9090
# The flowing code will register your server to eureka server and also start to send heartbeat every 30 seconds
eureka_client.init_registry_client(eureka_server=eureka_server_list,
                                app_name="your_app_name",
                                instance_host=your_rest_server_host,
                                instance_port=your_rest_server_port)
```

*上述方法中，你还可以传入本节点更多`Instance`对象的参数，请参考 eureka 接口定义或者代码。*

你还可以不传入`instance_host`参数，如果不传入那个参数，组件会根据当前的网络取得一个 ip 作为参数。

```Python
import py_eureka_client.eureka_client as eureka_client

your_rest_server_port = 9090
# The flowing code will register your server to eureka server and also start to send heartbeat every 30 seconds
eureka_client.init_registry_client(eureka_server="http://your-eureka-server-peer1,http://your-eureka-server-peer2",
                                app_name="your_app_name",
                                instance_port=your_rest_server_port)
```

*请注意，如果你将 python 组件和 eureka 服务器部署在一起，计算出来的 ip 会是 `127.0.0.1`，因此在这种情况下，为了保证其他组件能够访问你的组件，请必须指定`instance_host`或者`instance_ip`字段。*

### 发现服务

如果你的服务不对外提供服务，但是却需要调用其他组件的服务，同时也不需要让 eureka 管理组件状态，那么你可以仅使用发现服务，代码如下：

```python
import py_eureka_client.eureka_client as eureka_client

eureka_server_list = "http://your-eureka-server-peer1,http://your-eureka-server-peer2"
# you can reuse the eureka_server_list which you used in registry client
eureka_client.init_discovery_client(eureka_server_list)
```

无论你使用`init`还是`init_discovery_client`，初始化了发现服务之后，你就能通过以下方法来调用其他组件了。

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

# 统一注册接口
eureka_client.init(eureka_server=eureka_server_list,
                   app_name="your_app_name",
                   instance_port=9090,
                   ha_strategy=eureka_client.HA_STRATEGY_OTHER)
# 仅发现服务接口
eureka_client.init_discovery_client(eureka_server_list, ha_strategy=eureka_client.HA_STRATEGY_STICK)
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

### 退出

大部分情况下，如果你正常退出 python 应用程序，`py_eureka_client` 会自己停止并且向 eureka 服务器要求删除当前的节点实例（通过 @atexit 实现），但是，有时候你可能希望自己来控制退出的时机，那么你可以通过以下代码来实现：

```python
import py_eureka_client.eureka_client as eureka_client

eureka_client.stop()
```