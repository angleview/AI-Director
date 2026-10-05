# 安装与复现

本指南验证两层：无外设的测试与演示；真实 NCNN 推理和有限视频回放。回放使用虚拟执行器，不移动舵机。main.py 是历史摄像头/舵机原型，不是部署验证入口。

## 1 获取工程与环境

~~~bash
git clone https://github.com/angleview/AI-Director.git
cd AI-Director
~~~

核心要求 Python >=3.11。真实推理建议 CPython 3.11–3.13、64 位 Linux AArch64/x86_64 或 Windows x86_64。历史性能来自 Pi 5 / Debian 13 / Python 3.13.5；其他平台只验证功能，不能与 Pi 数字直接比较。

Linux / Raspberry Pi：

~~~bash
python3 -m venv .venv
source .venv/bin/activate
export PYTHONPATH=src
python -m pip install --upgrade pip
~~~

Windows PowerShell 不需要修改全局执行策略，直接指定虚拟环境解释器：

~~~powershell
python -m venv .venv
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m pip install --upgrade pip
~~~

以下 python 命令在 Windows 用 .venv/Scripts/python.exe 替换。在 Linux 先安装发行版的 python3-venv、python3-pip；OpenCV 若报 libGL.so.1 或 libgthread-2.0.so.0 缺失，Debian 13 可安装 libgl1、libglib2.0-0t64。其他发行版的包名可能不同。不要覆盖系统 Python 环境。

## 2 无外设快速验证

~~~bash
python scripts/prepare_assets.py model
python -m unittest discover -s tests -v
python -m edge_ai_director.demo
~~~

模型校验只使用标准库，不执行神经网络。历史 11 项核心测试另加 5 项资产验证测试，当前应为 16 项通过。演示输出七帧，模式依次 SEARCHING、TRACKING、LOCKED、LOCKED、LOCKED、TRACKING、TRACKING，最后 RESET。演示的 4 ms 来自虚拟时钟，不是实测速度。

## 3 安装真实推理依赖

~~~bash
python -m pip install -r requirements-inference.txt
python -c "import cv2, numpy, ultralytics, ncnn, torch, torchvision; print(cv2.__version__, numpy.__version__, ultralytics.__version__, torch.__version__)"
~~~

也可在可联网的虚拟环境用 python -m pip install -e ".[inference]" 安装项目与推理依赖。两种入口的关键版本保持一致。

| 依赖 | 运行配置 |
| --- | --- |
| NumPy | 2.2.4 |
| OpenCV | 4.12.0.88 |
| Ultralytics | 8.3.232 |
| NCNN | 1.0.20250916 |
| PyTorch / torchvision | 2.9.1 / 0.24.1 |

NCNN 执行网络计算，但 Ultralytics 包装器仍依赖 PyTorch 等库。历史 Pi 使用 torch 2.9.1；当前依赖文件固定六项直接依赖版本，并非完整传递依赖锁文件。本次 Windows 全新环境的版本清单与实测结果见 [发布验证](verification.md)；Linux 的传递依赖可能不同。需要严格复现实验环境时另保存 pip freeze 与系统信息。官方包支持与导出用法见 [NCNN 集成文档](https://docs.ultralytics.com/integrations/ncnn/)。

NCNN 若没有对应平台 wheel，会触发源码构建，需要 CMake、编译器等。先核对 Python 与平台；不要把构建失败误认为模型损坏。

如果用户配置目录没有写入权限，先建立工程内配置目录，再运行推理。Linux：

~~~bash
mkdir -p .local/yolo-config/Ultralytics
export YOLO_CONFIG_DIR="$PWD/.local/yolo-config"
export YOLO_AUTOINSTALL=false
~~~

Windows PowerShell：

~~~powershell
New-Item -ItemType Directory -Force .local/yolo-config/Ultralytics | Out-Null
$env:YOLO_CONFIG_DIR = (Resolve-Path .local/yolo-config).Path
$env:YOLO_AUTOINSTALL = 'false'
~~~

该目录不会纳入 Git。YOLO_AUTOINSTALL=false 让缺少依赖时直接报错，避免运行时自动安装。

## 4 获取完整模型并校验

完整 NCNN 模型随 Git 仓库发布，不需要登录、私有网盘或在运行时重新导出。目录 yolov8n-pose_ncnn_model 包含 param、bin、metadata；bin 约 6.86 MB。以下校验应全部通过：

~~~bash
python scripts/prepare_assets.py model
~~~

| 文件 | 字节数 | SHA-256 |
| --- | ---: | --- |
| model.ncnn.param | 20049 | 386d7c5800431655503e9e9182d8fd0a3cb6cb697ee14178e318ff850017f15f |
| model.ncnn.bin | 6860740 | a5835bb813fb284f2b18913adb9de28253539219b1f4d7e9d0c04b540850b8e3 |
| metadata.yaml | 423 | 9a437e69eef679f22b3faa30f3fb2a19aedef3b33769d701d721ac1f7119e480 |

校验数据保存在 assets/models/manifest.json，并与历史 Pi benchmark 中的三项资产一致。若校验不符，停止推理并检查下载/修改；脚本不会用其他模型静默替换。

模型基于 Ultralytics 官方 YOLOv8n-Pose 权重，导出元数据版本 8.3.225、原生输入 640×640、batch 1、half:true。完整历史导出命令未保留；附带生成文件不等于自研转换器。不要将当前版本的重新导出物说成与历史模型逐字节一致。

模型与依赖的授权说明见 [第三方来源](../THIRD_PARTY_NOTICES.md)。部署时使用 imgsz=640；480 失败对照不是推荐配置。

## 5 下载图片并生成回放

~~~bash
python scripts/prepare_assets.py input
python scripts/make_static_replay.py --image assets/inputs/bus.jpg --output assets/replays/bus-static-3s.avi --frames 30 --fps 10
~~~

下载来源与备用 HTTPS 地址记录在 assets/inputs/manifest.json。下载后必须匹配 SHA-256：

~~~text
c02019c4979c191eb739ddd944445ef408dad5679acab6fd520ef9d434bfbc63
~~~

现有正确图片不会重复下载；现有错误文件会明确报错并保持原样。图片未纳入 Git，通过公开来源获取。

回放生成器实际解码确认 30 帧，并打印新视频哈希、尺寸、帧率与时长。历史视频哈希为 53c0fd1e04958e0ed77e73333b2c05c644f66efce956d344a43476266c088355；不同 OpenCV/编解码构建不保证 AVI 二进制相同，因此应保留本次哈希并检查帧数和尺寸。文件已存在时请选择新输出名，不覆盖旧回放。

## 6 运行真实 NCNN

以下命令应在工程根目录执行。输出写入 results，它不会纳入版本控制；重跑时选择新文件名。

~~~bash
python -m edge_ai_director.benchmark --model yolov8n-pose_ncnn_model --source assets/inputs/bus.jpg --output results/benchmark-640.json --warmup 5 --runs 30 --imgsz 640 --conf 0.25
python -m edge_ai_director.replay --video assets/replays/bus-static-3s.avi --model yolov8n-pose_ncnn_model --output results/replay-640.jsonl --limit 30 --imgsz 640 --conf 0.25 --min-area 0.01
~~~

验收：

1. benchmark 记录 30 个 measurements，并含模型/图片哈希、环境、分阶段与总耗时。
2. 当前模型与固定图片应得到人体检测和 17 点姿态；历史 640 每轮为 4 个框。结果不同先核对资产与版本。
3. replay 输出 processed frames: 30，JSONL 序号 0–29，每帧一个控制意图，末行汇总。
4. 回放执行端始终为 VirtualActuator；不能以虚拟角度宣称物理运动。

本机速度和模式帧数不必与历史 Pi 完全相同。状态保持使用处理时钟，文件 10 fps 不会自动强制按媒体时间运行。

## 7 阅读历史证据

artifacts 中的 Pi 数值是历史测量，包含逐轮原始记录。公开副本仅移除主机身份和路径，保留数值、配置、哈希、环境软件版本和时间；变更范围见 [公开发布说明](public-release.md)。

640 的推理 P50/P95 76.60/77.22 ms；固定文件解码到 Results 为 91.49/92.97 ms，不包含摄像头、网页或舵机。30 帧静态回放证明计算链；动态场景、长期稳定性和实机控制另待验证。

旧原型硬件运行需要真实摄像头、合适供电及确认安全范围的云台。其附加依赖在 requirements.txt；本指南不要求启动 main.py。
