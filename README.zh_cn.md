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

由于考虑到一些组件只提供服务，不需要调用其他服务，因此设计时将注册和发现服务分离，因此你需要分别初始化注册和发现的服务端。

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

这个方法还接受其他的参数，剩余的参数和 `urllib2.urlopen` 接口一致。请参考相关的接口或者源代码进行传入。

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

### 仅发现服务

如果你的服务不对外提供服务，但是却需要调用其他组件的服务，同时也不需要让 eureka 管理组件状态，那么你可以仅使用发现服务，代码如下：

```python
import py_eureka_client.eureka_client as eureka_client

eureka_server_list = "http://your-eureka-server-peer1,http://your-eureka-server-peer2"
# you can reuse the eureka_server_list which you used in registry client
eureka_client.init_discovery_client(eureka_server_list)
```

之后，在你需要调用其他服务的业务代码中，使用以下的代码来获取服务：

```python
import py_eureka_client.eureka_client as eureka_client

res = eureka_client.do_service("OTHER-SERVICE-NAME", "/service/context/path", return_type="string")
print("result of other service" + res)

```

上述参数中，return_type 可以选择传入`json`，如果传入`json`，则该接口返回一个 `dict` 对象。该参数也可不传入，默认返回为 `str`。

这个方法还接受其他的参数，剩余的参数和 `urllib2.urlopen` 接口一致。请参考相关的接口或者源代码进行传入。

### 高可用

do_service 方法支持 HA（高可用），该方法会尝试所有从 ereka 服务器取得的节点，直至其中一个节点返回数据，或者所有的节点都尝试失败。

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