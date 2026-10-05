# 第一天：从零认识 Linux、Python 和项目核心

目标：运行核心；读懂一帧如何产生控制意图；知道程序、操作系统、硬件各负责什么。边读边执行，每个小节最后闭卷复述一次。

## 1. 先认识项目，而不是背技术名词

系统希望根据人的位置和姿态，改变画面构图或产生云台控制意图。它可以拆成五个问题：

1. 图像从哪里来？摄像头或视频文件。
2. 图里有什么？模型输出人体框、关键点。
3. 现在应该做什么？状态机决定跟踪、锁定、展示等模式。
4. 应该往哪里移动？控制器根据位置误差计算角度增量。
5. 如何执行和观察？舵机接口或虚拟执行器；原型还通过网页输出画面。

**旧原型**在 `main.py`，同时处理摄像头、模型、状态、控制、图像和网页。**实验核心**在 `src/edge_ai_director/`，先把各阶段做成可以独立验证的同步流水线。新核心没有实现完整的实时网页发布系统。

~~~text
原型：摄像头 → OpenCV 图像 → 推理/构图/控制 → JPEG → Flask → 浏览器
核心：Frame → Perception → Decision → ControlIntent → VirtualActuator
~~~

这一分钟的复述：“模型只负责给出每帧视觉信息。状态和控制是普通程序逻辑；控制意图也不代表舵机已经走到了指定位置。”

## 2. Linux、终端、Shell、Python 的区别

| 名称 | 含义 | 本项目对应 |
| --- | --- | --- |
| Linux 内核 | 管理 CPU 调度、内存、设备、文件等 | Pi 上的内核和设备接口 |
| Debian | 包含 Linux 内核和许多工具的软件发行版 | 历史设备清单里的 Debian 13 |
| 终端 | 输入命令并显示输出的界面 | 本地终端或 SSH 会话 |
| Shell | 解析命令的程序 | Linux 常用 Bash；当前 Windows 是 PowerShell |
| Python 解释器 | 运行 Python 程序 | 执行核心和实验入口 |
| 进程 | 一个正在运行的程序实例 | 一次 Python 程序运行 |

不要把 Bash 命令直接当 PowerShell 命令。先确认当前终端，再使用相应代码块。Linux 入门可查 [Debian Reference 的 GNU/Linux tutorials](https://www.debian.org/doc/manuals/debian-reference/ch01.en.html)；本教程只挑与项目相关的操作。

### 2.1 路径和文件

绝对路径从根位置开始；相对路径从当前目录开始。`src/edge_ai_director/domain.py` 的含义取决于当前目录。路径有空格时用引号。

Windows：

~~~powershell
Set-Location '.'
Get-Location
Get-ChildItem
Get-Content src/edge_ai_director/interfaces.py
~~~

Linux：先进入你实际保存工程的目录；`.` 是历史实验目录，存在时才能使用。

~~~bash
pwd
ls -la
cat src/edge_ai_director/interfaces.py
head -n 30 src/edge_ai_director/pipeline.py
~~~

解释：`pwd` 显示位置；`ls` 列文件；`cat` 看整个文件；`head` 看开头。这些都是读取操作。

如果装有 ripgrep，查调用位置：

~~~bash
rg -n "class|def " src/edge_ai_director/pipeline.py
rg -n "imencode|video_feed|VideoCapture" main.py
~~~

`-n` 显示行号；竖线在引号中的正则表达式表示“或”。没有 `rg` 时用编辑器搜索；不用为了读代码先安装一堆工具。

### 2.2 权限和设备

Linux 的 `rwx` 是读、写、执行。文件权限按所有者、所属组、其他人分组。目录的 `x` 主要决定能否进入/遍历，不等同于执行一个程序。

~~~bash
id
ls -l /dev/i2c-1
ls -l /dev/video*
~~~

`/dev` 中的节点是内核暴露的设备访问入口。节点存在不证明外设可用，更不证明程序实际使用了它。项目曾枚举到 HEVC 解码器节点，但没有摄像头；因此“有 /dev/videoX”不等于“有摄像头”。

`sudo` 用于权限提升，不能代替排查。遇到 Permission denied，应先确认节点归属、当前用户组和访问需求；不要默认改成所有人可写。

### 2.3 进程、CPU 和端口

~~~bash
uname -m
cat /etc/os-release
ps -ef
top
free -h
df -h
ss -ltn
~~~

| 命令 | 你在找什么 |
| --- | --- |
| `uname -m` | aarch64 等架构，决定二进制/轮子兼容性 |
| `os-release` | 发行版信息 |
| `ps`、`top` | 程序是否在运行、CPU 与内存 |
| `free` | RAM 与 swap |
| `df` | 磁盘空间，不是内存 |
| `ss -ltn` | TCP 监听端口；原型曾使用 5000 |

`top` 中按 `q` 退出；终端中 `Ctrl+C` 通常中断前台程序。这里不要求启动旧原型来观察端口。

### 2.4 SSH 和依赖

SSH 是远程安全登录，不是 Python 模块。只有确认自己的设备实际地址与账号后才连接：

~~~text
ssh 用户名@设备当前地址
~~~

不要直接照抄历史 IP。登录后执行的命令发生在远端 Pi，而不是电脑。

Python 模块依赖属于某个解释器环境。`python -m pip` 将 pip 与该解释器对应起来。虚拟环境把项目依赖与其他项目隔开，不是虚拟机。本课只运行标准库核心，不必安装机器学习依赖。可选环境：

~~~powershell
python -m venv .venv-learning
./.venv-learning/Scripts/python.exe --version
~~~

Linux 对应 `python3 -m venv .venv-learning`，解释器位于 `.venv-learning/bin/python`。若系统缺少 venv 支持，先继续用满足版本条件的现有解释器读核心，勿把学习时间耗在非必要环境安装上。

## 3. Python 基础：变量、对象和集合

先启动 `python` 或 `python3`，逐段输入；退出用 `exit()`。不要复制提示符 `>>>`。

~~~python
width = 640
x = 480
ratio = x / width
print(ratio)                 # 0.75
print(type(width).__name__)  # int
print(type(ratio).__name__)  # float
~~~

变量名指向对象；`=` 赋值，`==` 比较值。`/` 得到除法结果，`//` 是向下取整除法。图像位置计算必须保留小数。

~~~python
people = [0.2, 0.8]             # list：有顺序，可修改
people.append(0.5)
fixed = (640, 360)              # tuple：元素位置固定
by_frame = {7: "TRACKING"}       # dict：通过键查值
seen = {1, 1, 2}                # set：去重
print(sum(people) / len(people)) # 0.5
print(by_frame[7], seen)         # 集合显示次序不作为契约
~~~

字典查找缺失键会报 KeyError。`by_frame.get(8, "UNKNOWN")` 则使用默认值。项目脚本化推理使用帧序号查字典，因此帧号必须匹配。

### 3.1 引用与复制：面试高频坑

~~~python
a = [1, 2]
b = a
b.append(3)
print(a)      # [1, 2, 3]
c = a.copy()
c.append(4)
print(a)      # 仍是 [1, 2, 3]
~~~

`b=a` 没有复制列表。`copy()` 是浅复制；若元素又是列表，内层对象仍可能共享。OpenCV 图像通常是 NumPy 数组，原型 `frame.copy()` 会复制图像数据；这就是不能声称零拷贝的直接证据之一。

## 4. 分支、循环和函数：把计算写清楚

~~~python
def normalise(value: float, dimension: int) -> float:
    if dimension <= 0:
        raise ValueError("dimension must be positive")
    return max(0.0, min(1.0, value / dimension))

for x in [-10, 320, 900]:
    print(normalise(x, 640))
~~~

输出 `0.0, 0.5, 1.0`。每个函数有输入、处理、输出；`return` 返回结果；`raise` 报告不满足条件。缩进表示代码属于哪个块，统一使用四个空格。

`value: float` 和 `-> float` 是类型提示，通常不自动强制运行时类型。数据类中的 `__post_init__` 校验才是本项目实际的运行时检查。

~~~python
targets = [0.1, 0.7, 0.4]
large = [x for x in targets if x >= 0.3]
print(large)  # [0.7, 0.4]
~~~

这是列表推导式，等价于遍历、条件判断、append。看不懂时先改写成普通 for。

## 5. 类与实例：让状态有明确归属

~~~python
class Counter:
    def __init__(self, start: int = 0):
        self.value = start

    def next_value(self):
        current = self.value
        self.value += 1
        return current

counter = Counter(7)
print(counter.next_value())  # 7
print(counter.next_value())  # 8
~~~

类描述一类对象；实例保存某一份状态。`self` 是当前实例。`__init__` 初始化；`self.value` 跨调用保留。项目状态机保存上一个手势和当前模式，因此应理解它为什么需要一个对象。

`_mode` 的前导下划线表示内部使用约定，不是绝对的访问保护。`@property` 使只读访问可写为 `state_machine.mode`。

## 6. dataclass、Enum、Protocol：阅读核心所需语法

~~~python
from dataclasses import dataclass
from enum import Enum

class Mode(str, Enum):
    TRACKING = "TRACKING"
    LOCKED = "LOCKED"

@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float

point = Point(0.75, 0.4)
print(point.x, Mode.TRACKING.value)
~~~

dataclass 自动生成常用初始化和比较等方法；`frozen=True` 限制字段重新赋值；`slots=True` 为声明字段设置槽位，普通实例通常没有动态属性字典。它们不保证底层图像缓冲不可变：冻结的 Frame 仍可以持有可修改的数组。

Enum 把模式限定为有名字的成员，降低字符串拼写错误。核心用 `OperatingMode.TRACKING` 等明确表达模式。

`interfaces.py` 的 Protocol 描述“对象需要提供什么方法”。FrameSource 有 read，InferenceBackend 有 infer，Actuator 有 apply。一个类不必继承 Protocol，只要结构匹配，静态类型工具即可按接口使用；普通类型提示本身不自动执行接口验证。

**依赖注入**就是把 source、backend、clock、actuator 等依赖通过参数传进来。可换成视频源和真实模型，也可换成确定性脚本与虚拟时钟。不是在算法中到处检查“是不是测试模式”。

## 7. 生成器、模块、异常与文件

~~~python
def frames():
    for sequence in range(3):
        yield sequence

iterator = frames()
print(next(iterator)) # 0
print(list(iterator)) # [1, 2]：0 已经取走
~~~

`yield` 产出一个值并暂停，下一次迭代从暂停处继续。生成器通常节省一次性保存全部结果的内存；生成器自身不等于线程或并行计算。核心 `pipeline.run()` 顺序处理并逐帧 yield。

模块是 Python 文件；包组织多个模块。`from .domain import Frame` 的点表示包内相对导入。正确运行入口：

~~~powershell
$env:PYTHONPATH = 'src'
python -m edge_ai_director.demo
~~~

`PYTHONPATH` 让解释器在 src 查找包。`-m` 按模块名运行，保留包上下文；不要直接运行包里的 demo.py 后再临时乱改导入。

`if __name__ == "__main__":` 区分被直接运行和被别的模块导入。新核心避免在导入时打开硬件。

~~~python
from pathlib import Path
import json

report_path = Path("artifacts/benchmarks/pi5-yolov8n-pose-ncnn-bus-img640.json")
with report_path.open(encoding="utf-8") as stream:
    report = json.load(stream)
print(report["configuration"]["measured_runs"])  # 30
~~~

`with` 保证离开作用域时释放文件等资源。捕获异常应针对可处理的问题，例如 FileNotFoundError；不应写 `except: pass` 把模型损坏、权限错误和代码错误都当成功。

Python 语法深入参考 [Python 官方教程](https://docs.python.org/3.13/tutorial/)；本课示例专门为项目学习编写，不要求先通读整本手册。

## 8. 按数据顺序读真实代码

在编辑器打开以下文件，每个文件先找 class 和 def，再追方法内部。

| 文件 | 阅读任务 | 用一句话概括 |
| --- | --- | --- |
| domain.py | Frame、Perception、Decision、ControlIntent | 各阶段交换明确数据 |
| interfaces.py | read/infer/apply 的签名 | 规定依赖边界 |
| simulated.py | read 的结束条件、infer 的帧号、apply 的限位 | 无外设验证逻辑 |
| state_machine.py | update | 当前状态和观测产生决策 |
| control.py | plan | 决策和位置产生控制意图 |
| pipeline.py | step 与 run | 顺序串联并计时 |
| demo.py | 七帧与手势序列 | 确定性演示整个核心 |

### 一次 step 的执行顺序

1. 保存开始时间，source.read 得到 Frame；None 表示没有下一帧。
2. backend.infer 得到 Perception；核对结果帧号是否等于输入帧号。
3. state_machine.update 更新模式；controller.plan 计算 ControlIntent。
4. actuator.apply 应用意图；虚拟执行器只更新内存角度和日志。
5. 计算各阶段时间并返回 PipelineResult。

为什么核对帧号？把第 10 帧的人体位置用于第 11 帧控制，可能控制错误目标。当前检查用于同一次同步调用；未来并发系统还需要过期结果丢弃、时间戳和执行顺序等规则。

为什么用单调时钟？计算间隔不应被系统时间校准影响。`monotonic_ns` 的绝对数值无需转换成日期，只计算差值；1 ms = 1,000,000 ns。

## 9. 第一次运行与解释

按总入口执行测试和 demo。历史核心为 11 项；当前含资产检查共 16 tests / OK；演示为七行：

| 帧 | 模式 | 动作 | 解释 |
| --- | --- | --- | --- |
| 0 | SEARCHING | HOLD | 无人 |
| 1 | TRACKING | RELATIVE_MOVE | 出现目标 |
| 2 | LOCKED | HOLD | 左手首次举起 |
| 3 | LOCKED | HOLD | 左手保持，不重复切换 |
| 4 | LOCKED | HOLD | 放下，模式仍锁定 |
| 5 | TRACKING | RELATIVE_MOVE | 再举左手，解锁 |
| 6 | TRACKING | RESET | 双手举起边沿，请求复位 |

demo 的 `total_ms=4.0` 来自每次前进 1 ms 的虚拟时钟。不是 CPU 实测；不能写成“树莓派 4 ms 完成推理”。

测试阅读：先看测试名、准备的数据、调用，再看 assert。test_real_pipeline 使用 FakeCV2/FakeModel 验证适配逻辑，名称中的 real 不代表测试正在跑 NCNN。真实 NCNN 证据来自 Pi 产物。

## 10. 动手任务与验收

运行学习脚本：

~~~powershell
python docs/learning/three-day-bootcamp/practice.py python
python docs/learning/three-day-bootcamp/practice.py core
~~~

先不看答案，完成：用普通 for 计算目标 x 的平均值；重写 normalise；解释为什么需要判断空列表。再检查脚本对应函数。

闭卷自测及答案：

1. **为什么设置 PYTHONPATH？**包位于 src，需要加入模块查找路径。
2. **Frame payload 是什么？**图像载荷；模拟帧可以没有图像，但真实推理要求图像。
3. **Perception 是跟踪身份吗？**只是当前帧观测，没有跨帧 ID 保持。
4. **ControlIntent 与动作差别？**期望动作与实际物理响应不同，当前虚拟记录不能证明机械运动。
5. **frozen 能保护数组吗？**不提供深层不可变保证。
6. **Protocol 为什么有用？**按 read/infer/apply 边界替换依赖，便于确定性验证。
7. **yield 会启动线程吗？**不会，它控制迭代和暂停。
8. **为什么测试超时不用 sleep 30 秒？**注入时间，直接构造边界时间点，稳定且快速。
9. **为何模型导入延后到适配器初始化？**核心可在没有大型依赖的环境运行。
10. **一次 step 有几个控制意图？**当前同步实现每个成功输入产生一个意图，执行器接收一次。

答对至少 8 题，能定位到源码，进入第二天。
