> 本文公开副本已脱敏主机元信息；当前复现请先按 docs/deployment.md 获取环境与输入。

# Raspberry Pi 5 NCNN 基线与输入尺寸对照

## 结论

在 Raspberry Pi 5 的 4 核 Cortex-A76 CPU 上，YOLOv8n-Pose NCNN 导出模型以其原生 `640×640` 输入运行时，固定图片到 `Results` 的端到端延迟 P50/P95 为 **91.49/92.97 ms**，其中 NCNN 推理 P50/P95 为 **76.60/77.22 ms**。30 次测量均返回 4 个检测，温度由 52.7°C 上升至 55.4°C，前后均未报告欠压或降频。

把运行参数单独改为 `imgsz=480` 并没有带来端到端优化。虽然框架上报的推理 P50 降至 42.17 ms，但最终输出检测框由 4 增至 300，后处理 P50 从 1.57 ms 增至 1113.33 ms，最终端到端 P50 达 1229.42 ms，是 640 配置的 13.44 倍。因此项目保留 640 配置。

## 设备与软件

- Raspberry Pi 5 Model B Rev 1.1，8 GB，AArch64，4× Cortex-A76。
- Python 3.13.5，Ultralytics 8.3.232，NCNN 1.0.20250916，OpenCV 4.12.0.88。
- YOLOv8n-Pose NCNN：`model.ncnn.param` 20,049 字节，`model.ncnn.bin` 6,860,740 字节。
- 模型 `metadata.yaml` 声明 `imgsz: [640, 640]`、`batch: 1`、`half: true`。
- 固定输入 `bus.jpg`：810×1080，SHA-256 `c02019c4979c191eb739ddd944445ef408dad5679acab6fd520ef9d434bfbc63`。

## 测量方法

两组实验都执行 5 次不计入统计的预热和 30 次正式测量，置信度为 0.25。每轮重新从文件解码图片，再调用同一个已加载模型对象。报告保留每一轮原始值，并对下列边界分别统计 P50、P95 和 P99：

- OpenCV 文件解码。
- Ultralytics 报告的预处理、推理与后处理。
- `model.predict()` 外部墙钟时间。
- 从开始解码到拿到 `Results` 的端到端墙钟时间。

640 原始报告：[pi5-yolov8n-pose-ncnn-bus-img640.json](../../artifacts/benchmarks/pi5-yolov8n-pose-ncnn-bus-img640.json)。

480 原始报告：[pi5-yolov8n-pose-ncnn-bus-img480.json](../../artifacts/benchmarks/pi5-yolov8n-pose-ncnn-bus-img480.json)。

## 分阶段结果

| 指标（ms） | 640 P50 | 640 P95 | 480 P50 | 480 P95 |
|---|---:|---:|---:|---:|
| 文件解码 | 5.88 | 5.96 | 6.03 | 6.47 |
| 预处理 | 7.05 | 7.78 | 4.34 | 4.77 |
| NCNN 推理 | 76.60 | 77.22 | 42.17 | 170.34 |
| 后处理 | 1.57 | 2.11 | 1113.33 | 1256.59 |
| `predict()` 墙钟 | 85.57 | 87.09 | 1223.37 | 1393.82 |
| 文件到结果端到端 | 91.49 | 92.97 | 1229.42 | 1400.26 |
| 每轮检测数 | 4 | 4 | 300 | 300 |

## 为什么局部变快、系统反而变慢

480 配置的推理 P50 比 640 低 44.9%，但最终输出检测框数异常增至 300，后处理成为主要耗时。报告没有记录 NMS 前候选数，也没有完全隔离根因。已有结果支持拒绝该运行配置；固定导出形状、输出解码假设等原因仍需通过原生 480 导出与正确性对照验证，不能将相关性写成确定因果。

这次实验说明不能只引用推理引擎内部耗时。端侧优化必须同时检查端到端延迟、尾延迟和输出语义，否则会把“局部算得更快但整体不可用”误判成优化。

## 真实回放验证

使用固定图片生成了 810×1080、10 FPS、30 帧、3 秒的 MJPEG AVI。生成后反向解码得到 30 帧，视频 SHA-256 为 `53c0fd1e04958e0ed77e73333b2c05c644f66efce956d344a43476266c088355`。

在 640 配置下，30 帧全部经过 OpenCV 解码、真实 NCNN 推理、状态机、多人构图控制器和虚拟执行器：序号连续为 0–29，每帧保留 2 个目标并生成一个控制记录；前 22 帧为 `TRACKING`，姿态持续达到 2 秒后，后 8 帧进入 `SHOWCASE`。流水线总延迟 P50/P95 为 **92.85/99.12 ms**。

逐帧证据：[pi5-bus-static-img640.jsonl](../../artifacts/replays/pi5-bus-static-img640.jsonl)。静态回放只验证解码、推理、状态和控制调用链，不证明运动跟踪效果、模型准确率或机械控制精度。

## 可复现命令

```bash
cd .

PYTHONPATH=src python3 -m edge_ai_director.benchmark \
  --model yolov8n-pose_ncnn_model \
  --source assets/inputs/bus.jpg \
  --output results/benchmark-640.json \
  --warmup 5 --runs 30 --imgsz 640 --conf 0.25

python3 scripts/make_static_replay.py \
  --image assets/inputs/bus.jpg \
  --output assets/replays/bus-static-3s.avi --frames 30 --fps 10

PYTHONPATH=src python3 -m edge_ai_director.replay \
  --video assets/replays/bus-static-3s.avi \
  --model yolov8n-pose_ncnn_model \
  --output results/replay-640.jsonl \
  --limit 30 --imgsz 640 --conf 0.25 --min-area 0.01
```

## 后续实验

1. 从原始 `.pt` 模型分别导出真正的 640 和 480 NCNN 模型，再比较等价输出下的延迟。
2. 延长到 10 分钟，采样温度、频率、RSS 和尾延迟，验证热稳定性。
3. 用含动作和遮挡的授权视频验证状态切换和目标选择，而不是重复静态帧。
4. 对一个预处理热点实现 C++ 标量与 ARM NEON 版本，比较输出一致性和周期消耗。
