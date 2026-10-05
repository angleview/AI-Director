# 公开发布前的实际验证

验证日期：2026-10-05。验证对象为本次公开快照；使用 Windows 11、64 位 Python 3.13.5，在全新虚拟环境安装 requirements-inference.txt，没有继承系统 site-packages。这次验证没有连接树莓派、摄像头或舵机。

## 执行与结果

| 检查 | 实际结果 |
| --- | --- |
| 全新环境安装 | 六项直接依赖安装成功，pip check 无冲突 |
| 项目安装入口 | pip install -e ".[inference]" 成功，pip check 无冲突 |
| 模型校验 | param/bin/metadata 字节数及 SHA-256 全部通过，与历史 Pi 报告一致 |
| 公共图片下载 | 通过公开 HTTPS 实际下载，SHA-256 与输入清单一致 |
| 静态视频生成 | 810×1080、10 fps、30 帧、3 秒；生成后实际解码检查 |
| 标准库测试 | 16 项全部通过 |
| 虚拟演示 | 7 帧及手势锁定、解锁、复位通过 |
| 真实 NCNN benchmark | 5 次预热、30 次正式测量；每轮 4 个检测框，均含姿态关键点 |
| 真实 NCNN 回放 | 顺序处理 30 帧，序号 0–29，每帧一个控制意图，执行端为 VirtualActuator |

直接依赖实际版本为 NumPy 2.2.4、OpenCV 4.12.0.88、Ultralytics 8.3.232、NCNN 1.0.20250916、PyTorch 2.9.1、torchvision 0.24.1。完整本机版本记录见 [Windows freeze](../artifacts/verification/requirements-windows-python313.txt)，仅用于该平台追溯，不代替跨平台安装入口。

## 公开原始记录

- [Windows 30 轮 benchmark](../artifacts/benchmarks/windows-clean-install-img640.json)
- [Windows 30 帧回放](../artifacts/replays/windows-clean-install-img640.jsonl)
- [历史 Pi 实验报告](experiments/2026-08-07-pi5-ncnn-baseline.md)

Windows 本次推理 P50/P95 为 38.75/40.87 ms，文件解码到 Results 为 46.02/48.69 ms。它只说明当前平台能够运行，不用于替代历史 Pi 性能。本次生成 AVI 的 SHA-256 为：

~~~text
65bcac5406637602358102b3521b8197ea12a1a6b76781ad8fbfcffb964f44a1
~~~

该哈希对应本次 Windows 编码输出；其他 OpenCV 构建生成的视频可有不同哈希，仍须检查帧数、尺寸与内容来源。

## 复现步骤与限制

按 [部署说明](deployment.md) 从模型校验、图片下载、回放生成依次执行到 benchmark 和 replay。本次环境设置了工程内的 YOLO_CONFIG_DIR，并关闭运行时自动安装；两项设置的完整命令也在部署说明中。

报告仅脱敏主机名与绝对路径，并显式标注 metadata_redacted；数值、配置、哈希与时间保持原样。发布不携带原开发仓库历史及内部运行状态。树莓派本次重新部署、动态视频、摄像头采集、网络传输、实际舵机和长时稳定性尚未验证。
