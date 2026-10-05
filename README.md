# AI Director

基于 Raspberry Pi 5 的端侧姿态感知与智能构图项目。使用 YOLOv8n-Pose / NCNN，将图像转换为目标与手势观测，再由状态机和控制器产生云台控制意图。仓库提供完整模型、测试、固定输入基准和静态回放证据。

## 项目结构

- main.py：历史摄像头、PCA9685 双轴舵机、Flask/MJPEG 原型；不由新核心导入。
- src/edge_ai_director：可替换输入/模型/执行器的同步参考核心。
- tests：历史 11 项核心测试及新增 5 项资产校验测试。
- yolov8n-pose_ncnn_model：完整 NCNN param/bin/metadata，约 6.86 MB 权重。
- scripts：模型校验、公共图片下载和有限 MJPEG 回放生成。
- artifacts：公开脱敏后的历史 Pi 实验原始轮次及逐帧记录。

~~~mermaid
flowchart LR
    A[图像 Frame] --> B[NCNN 姿态观测 Perception]
    B --> C[状态机 Decision]
    B --> D[构图控制 ControlIntent]
    C --> D
    D --> E[虚拟执行器 位置与日志]
~~~

## 克隆与快速验证

Python >=3.11。先验证标准库核心，不要求摄像头、舵机或推理依赖。

~~~bash
git clone https://github.com/angleview/AI-Director.git
cd AI-Director
~~~

Linux / Raspberry Pi：

~~~bash
export PYTHONPATH=src
python3 scripts/prepare_assets.py model
python3 -m unittest discover -s tests -v
python3 -m edge_ai_director.demo
~~~

Windows PowerShell：

~~~powershell
$env:PYTHONPATH = 'src'
python scripts/prepare_assets.py model
python -m unittest discover -s tests -v
python -m edge_ai_director.demo
~~~

当前预期 16 项测试通过；演示输出 7 帧，包含举手锁定、保持、释放后再次解锁及复位。演示的 total_ms=4.0 是虚拟时钟结果，不是设备性能。

## 真实 NCNN 推理与回放

推荐 64 位 CPython 3.11–3.13。先建立虚拟环境，再安装 requirements-inference.txt，避免改动系统 Python。Linux 示例：

~~~bash
python3 -m venv .venv
source .venv/bin/activate
export PYTHONPATH=src
python -m pip install -r requirements-inference.txt
python scripts/prepare_assets.py all
python scripts/make_static_replay.py --image assets/inputs/bus.jpg --output assets/replays/bus-static-3s.avi --frames 30 --fps 10
python -m edge_ai_director.benchmark --model yolov8n-pose_ncnn_model --source assets/inputs/bus.jpg --output results/benchmark-640.json --warmup 5 --runs 30 --imgsz 640 --conf 0.25
python -m edge_ai_director.replay --video assets/replays/bus-static-3s.avi --model yolov8n-pose_ncnn_model --output results/replay-640.jsonl --limit 30 --imgsz 640 --conf 0.25 --min-area 0.01
~~~

Windows 虚拟环境命令、系统依赖、排查方法与完整验收见 [部署说明](docs/deployment.md)。运行使用 VirtualActuator，不移动舵机。生成文件写入被忽略的目录；再次运行请换输出文件名。

发布前已在 Windows / Python 3.13.5 的全新虚拟环境验证依赖安装、图片下载、回放生成、30 次真实 NCNN 推理及 30 帧回放；16 项测试通过。平台、版本和脱敏原始记录见 [发布验证](docs/verification.md)。

## 模型和素材获取

完整模型直接随 Git 克隆，无需私有地址或重新导出；运行 python scripts/prepare_assets.py model 核对三个文件。完整大小与校验表见 [部署说明](docs/deployment.md#4-获取完整模型并校验) 和 [模型清单](assets/models/manifest.json)。

关键 SHA-256：

~~~text
model.ncnn.bin
a5835bb813fb284f2b18913adb9de28253539219b1f4d7e9d0c04b540850b8e3

bus.jpg
c02019c4979c191eb739ddd944445ef408dad5679acab6fd520ef9d434bfbc63
~~~

图片通过 scripts/prepare_assets.py input 从公开 HTTPS 来源获取并校验，不纳入 Git。回放脚本解码检查生成的 30 帧，输出本次 SHA-256；不同编解码构建的 AVI 哈希可能不同。来源与授权见 [第三方说明](THIRD_PARTY_NOTICES.md)。

## 历史 Raspberry Pi 5 结果

固定 bus.jpg、原生 640 NCNN、conf=0.25、5 次预热和 30 次正式测量：

| 指标 | P50 | P95 |
| --- | ---: | ---: |
| NCNN 推理 | 76.60 ms | 77.22 ms |
| 文件解码到 Results | 91.49 ms | 92.97 ms |
| 30 帧静态回放核心总耗时 | 92.85 ms | 99.12 ms |

[实验报告](docs/experiments/2026-08-07-pi5-ncnn-baseline.md)保留 640/480 负向对照；[benchmark JSON](artifacts/benchmarks/pi5-yolov8n-pose-ncnn-bus-img640.json)和[回放 JSONL](artifacts/replays/pi5-bus-static-img640.jsonl)保留原始轮次。公开副本仅脱敏设备身份与路径，见[公开发布说明](docs/public-release.md)。

固定文件端到端不包含摄像头、网页、网络或实际舵机。静态回放不能证明动态身份跟踪或机械精度；本机重测速度不应替代历史 Pi 数字。

## 阅读代码与学习

- [领域对象与同步核心](docs/learning/01-testable-core.md)
- [真实 NCNN 基准](docs/learning/02-first-real-inference.md)
- [模型到控制回放](docs/learning/03-replay-to-control.md)
- [三天学习大纲与教程](docs/learning/three-day-bootcamp/README.md)
- [原型审计](docs/audits/2026-08-06-code-audit.md)
- [领域术语](CONTEXT.md)与[架构决策](docs/adr/)

已验证的范围为计算核心、资产完整性、NCNN 固定输入与虚拟控制链路。RTOS、H.265 转 MJPEG、持续 1080p 30 FPS、ReID、完整 PID、机械精度和长时稳定性不属于当前已验证成果。
