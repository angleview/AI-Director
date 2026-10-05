# 三天项目学习与秋招训练：入口和学习大纲

适用对象：编程、Linux 和端侧 AI 基础较弱，计划连续三天、每天约 10 小时学习，希望能够介绍项目、读懂关键代码并应对追问。

30 小时的合理目标是建立完整解释能力并完成基础练习。Linux 内核、C/C++、深度学习训练和 RTOS 需要后续专项学习；这份教程不会把完成阅读等同于完全掌握。

## 1. 学完要交付什么

1. 不看资料画出两条链路：原型摄像头到网页；实验核心 Frame 到虚拟执行器。
2. 独立运行核心测试、演示和附带练习，解释输出。
3. 手算坐标归一化、手势边沿、比例控制和 P95。
4. 说清 640 基线、480 失败对照的条件、结果和限制。
5. 完成 30 秒、90 秒、5 分钟项目介绍；回答至少 20 道核心追问。
6. 完成两道基础编程题，能说明时间复杂度与边界条件。
7. 区分代码存在、设备实测、仿真验证、未来设想和个人真实贡献。

验收用“能运行、能手算、能讲清、能定位源码”，不能仅用“已经看过”。

## 2. 学习材料

| 顺序 | 教程 | 学习用途 |
| --- | --- | --- |
| 1 | [第一天：Linux、Python 与核心代码](01-linux-python-core.md) | 从终端、变量和函数起步，读通同步流水线 |
| 2 | [第二天上半场：视觉、状态机与控制](02-vision-state-control.md) | 理解姿态输出、几何手势、状态迁移与角度计算 |
| 3 | [第二天下半场及第三天基础：视频、并发与测量](03-media-linux-benchmark.md) | MJPEG、Flask、线程锁、Linux 硬件接口、性能证据 |
| 4 | [第三天：笔试、岗位特化与项目表达](04-written-and-interview.md) | 编程练习、C/RTOS 补充、项目介绍和模拟流程 |
| 5 | [40 道深度追问与参考答案](05-deep-questions.md) | 先答再核对，形成自己的回答 |
| 6 | [可运行学习练习](practice.py) | 只使用标准库与现有核心；不打开摄像头、不移动舵机 |

已有三课可作为补充：[同步核心](../01-testable-core.md)、[真实推理](../02-first-real-inference.md)、[回放到控制](../03-replay-to-control.md)。其中“扩展功能”练习不是这次学习的必做项。

## 3. 每天 10 小时的安排

以下为有效学习时间；吃饭和短休息不计入。建议每 50 分钟休息 10 分钟，不要求连续坐满 10 小时。

| 天 | 时段 | 工作 | 必须留下的结果 |
| --- | --- | --- | --- |
| 1 | 0–1 h | 项目地图、运行环境、第一次演示 | 保存测试与演示结果 |
| 1 | 1–3 h | Linux 路径、权限、进程、环境与 SSH | 解释 10 个常用命令 |
| 1 | 3–5.5 h | Python 数据、分支循环、函数、类、异常 | 手写一个归一化函数和一个简单类 |
| 1 | 5.5–8 h | dataclass、Enum、Protocol、生成器、核心调用链 | 画出对象流和调用顺序 |
| 1 | 8–10 h | 核心练习、测试阅读、闭卷复述 | 第一天验收题通过 |
| 2 | 0–2 h | 图像数组、YOLO Pose、NCNN、模型资产 | 从一帧到 Perception 的解释 |
| 2 | 2–4 h | 状态机、手势边沿、P 控制、执行边界 | 一张迁移表和一次控制手算 |
| 2 | 4–6 h | 原型摄像头、MJPEG、Flask、多客户端问题 | 原型链路图与改进设计草图 |
| 2 | 6–8 h | 基准程序、P50/P95、640/480 对照 | 用脚本复算已有报告 |
| 2 | 8–10 h | 回放证据、前 20 道追问、第二天验收 | 能讲出失败对照的价值 |
| 3 | 0–2 h | 进程线程、I²C/PWM、ARM、RTOS 边界 | Linux 和硬件基础题答案 |
| 3 | 2–4 h | Python 笔试题、C 基础补充 | 至少独立完成两道题 |
| 3 | 4–6 h | 三种长度介绍、岗位特化、后 20 道追问 | 录制介绍并标出卡顿点 |
| 3 | 6–8 h | 两轮模拟面试、追到源码或证据 | 错题与缺口清单 |
| 3 | 8–10 h | 修正错误、最终验收 | 通过下列验收表 |

时间不足时先保证核心链路、状态机、控制、性能证据和介绍练习。C、RTOS 补充只建立基础认知，不能在三天内形成该方向的完整竞争力。

## 4. 从这里开始：只有电脑也能学习

在 Windows PowerShell 中执行：

~~~powershell
Set-Location '.'
python --version
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -v
python -m edge_ai_director.demo
python docs/learning/three-day-bootcamp/practice.py all
~~~

Python 要求至少 3.11。前三种学习运行不需要安装 PyTorch、NCNN、OpenCV 或 Flask。若机器使用 `py` 而非 `python`，使用已安装且满足版本条件的解释器替换命令。

在 Linux/Pi 上，先进入实际工程目录，再执行：

~~~bash
export PYTHONPATH=src
python3 --version
python3 -m unittest discover -s tests -v
python3 -m edge_ai_director.demo
python3 docs/learning/three-day-bootcamp/practice.py all
~~~

当前学习材料编写时，本机 Python 3.14.6 下已有 11 项测试通过。Pi 历史实验使用 Python 3.13.5；本机测试通过不能替代重新验证真实 Pi 推理环境。

## 5. 两种练习路径

**只有电脑：**运行核心与学习脚本，阅读保存的 Pi JSON/JSONL，复算统计并解释适配器测试。这里运行的 ScriptedInferenceBackend 和 FakeModel 没有执行神经网络。

**有 Pi：**先完成电脑路径，再检查实际连接、依赖和完整模型。在具备条件时按第三篇教程重新运行固定输入实验，使用新文件保存结果。当前仓库本地缺少 NCNN 的 `model.ncnn.bin`，不能保证克隆后直接做真实推理。历史设备清单也不代表设备现在仍可访问。

不把启动原型 `main.py` 作为第一步：它在导入和初始化期间涉及硬件、模型与后台线程，学习同步核心更容易定位问题。

## 6. 源码与证据地图

~~~mermaid
flowchart LR
    A["输入源 Frame"] --> B["模型适配 Perception"]
    B --> C["状态机 Decision"]
    B --> D["控制器 ControlIntent"]
    C --> D
    D --> E["虚拟执行器 位置与记录"]
~~~

该图表示同步实验核心；物理舵机和网页输出需要各自接入与验证。

下表路径均相对于 `edge-ai-lab`，用于在编辑器查找。

| 内容 | 去哪里看 | 能证明的范围 |
| --- | --- | --- |
| 领域术语 | `CONTEXT.md`、`src/edge_ai_director/domain.py` | 系统数据及含义 |
| 同步核心 | `interfaces.py`、`pipeline.py`、`demo.py` | 一帧经过各阶段的实现 |
| 状态与控制 | `state_machine.py`、`control.py`、`simulated.py` | 逻辑迁移、控制意图、虚拟限位 |
| 真实模型适配 | `ultralytics_backend.py`、`replay.py` | OpenCV/模型边界与回放入口 |
| 原始摄像头原型 | `main.py` | 线程、网页、JPEG 编码和 ServoKit 调用 |
| 单元测试 | `tests/` | 已覆盖的确定性行为 |
| 设备 | `artifacts/baselines/2026-08-06-device-inventory.md` | 当时的 Pi/系统/外设状态 |
| 真实性能 | `artifacts/benchmarks/pi5-yolov8n-pose-ncnn-bus-img640.json`、`artifacts/benchmarks/pi5-yolov8n-pose-ncnn-bus-img480.json` | 固定图片与配置下的短测 |
| 真实回放 | `artifacts/replays/pi5-bus-static-img640.jsonl` | 静态 30 帧 NCNN 到虚拟执行器 |
| 实验解释 | `docs/experiments/2026-08-07-pi5-ncnn-baseline.md` | 方法、发现与尚未隔离的原因 |

源码文件名未写目录时默认位于 `src/edge_ai_director/`。旧原型和新核心是两条实现，不应混写成一条已打通的实时生产链路。

## 7. 最终验收与复习规则

- [ ] 独立运行 11 项测试、7 帧演示和学习脚本。
- [ ] 闭卷解释 Frame → Perception → Decision → ControlIntent → Actuator。
- [ ] 解释 Enum、dataclass、Protocol、生成器及异常的用途。
- [ ] 手算目标 `(0.8, 0.6)` 的单人控制结果：pan `+4°`，tilt `+3.24°`。
- [ ] 解释持续举手为何不应每帧切换，以及现有边沿规则的抗抖局限。
- [ ] 说出 640 推理 P50/P95 `76.60/77.22 ms`，固定图片端到端 `91.49/92.97 ms`。
- [ ] 解释 480 推理变快但后处理拖慢总链路，不能宣布优化成功。
- [ ] 正确回答 RTOS、H.265、零拷贝、PID、ReID、物理闭环、30 FPS 七类边界。
- [ ] 40 道题抽 20 道，至少 16 道达到“原理＋项目对应＋限制”。
- [ ] 无提示完成两道编程题，覆盖空输入或边界值。
- [ ] 录制 90 秒和 5 分钟介绍；每项个人贡献都能指出真实依据。

答错时回到对应代码或实验记录，再用自己的话回答。背诵参考答案但不能解释变量变化，视为未通过。进度可记到新建的 `tasks/three-day-interview-learning.md`。
