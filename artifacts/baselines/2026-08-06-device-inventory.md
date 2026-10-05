> 历史设备记录；本次发布已补齐完整模型，当前部署见 [部署说明](../../docs/deployment.md)。

# Raspberry Pi 设备基线（2026-08-06）

## 采集范围

通过 `scripts/device_inventory.sh` 经 SSH 只读采集。此次只确认设备环境和硬件可见性，没有安装依赖、上传工程、运行模型或驱动舵机，因此还不是性能基线。

## 硬件与系统

| 项目 | 实测值 |
| --- | --- |
| 设备 | Raspberry Pi 5 Model B Rev 1.1 |
| CPU | 4× ARM Cortex-A76，最高 2.4 GHz |
| 指令集 | AArch64，包含 ASIMD/NEON、FP16、dot-product |
| 内存 | 8,454,684,672 bytes（约 7.87 GiB） |
| 存储 | 30,167,474,176 bytes；已用 33% |
| 系统 | Debian GNU/Linux 13 (trixie) |
| 内核 | 6.12.47+rpt-rpi-2712，aarch64 |
| 网络 | Wi-Fi `redacted/24`；以太网未连接 |

## 空闲状态

| 项目 | 实测值 |
| --- | --- |
| CPU 当前频率 | 1.8 GHz（另一次采样为 2.4 GHz） |
| 温度 | 46.3–47.7°C |
| 降频标志 | `0x0`，未发生欠压或热降频 |
| 可用内存 | 约 7.14 GiB |
| Swap 使用 | 0 |
| 系统负载 | 约 0.13 / 0.17 / 0.22 |

这些数值只是空闲快照，不能用于宣称模型性能或持续运行稳定性。

## 设备与接口

- USB 总线只枚举到四个 root hub，没有外接 USB 摄像头。
- `rpicam-hello --list-cameras` 返回 `No cameras available!`。
- 没有 `/dev/video0`；`/dev/video19`–`/dev/video35` 属于 HEVC 解码器和 PiSP 后端，不是可直接替代 `/dev/video0` 的摄像头。
- `/dev/i2c-1`、`/dev/i2c-13`、`/dev/i2c-14` 存在，但 `i2cdetect` 尚未安装。
- 设备用户 已属于 `video`、`i2c`、`gpio`、`spi`、`render` 等组，现有权限结构适合后续无 root 访问硬件。

## 软件环境

| 组件 | 实测版本 |
| --- | --- |
| Python | 3.13.5 |
| pip | 25.1.1 |
| OpenCV | 4.12.0.88 |
| NumPy | 2.2.4 |
| Flask | 3.1.1 |
| Ultralytics | 8.3.232 |
| Adafruit ServoKit | 1.3.22 |
| NCNN Python | 1.0.20250916 |
| PyTorch | 2.9.1 |

## 模型资产

树莓派存在两份相同层级结构的 NCNN 模型候选：

- `yolov8n-pose_ncnn_model/model.ncnn.{param,bin}`
- `yolov8n-pose_ncnn_model/yolov8n-pose_ncnn_model/model.ncnn.{param,bin}`

`model.ncnn.bin` 大小为 6,860,740 bytes，`model.ncnn.param` 大小为 20,049 bytes。本机工程副本缺少 `.bin`，因此部署过程目前不可复现，且树莓派上的重复目录容易造成模型路径歧义。

## 当前结论

1. 树莓派本体、AArch64 Python 环境和模型运行依赖具备继续实验的基础。
2. 摄像头当前不可见，原型中的 `VideoCapture(0)` 无法建立真实视频基线。
3. I²C 设备节点和用户组权限已具备，但尚未确认 PCA9685/ServoKit 地址，也不能安全移动舵机。
4. 下一次设备实验应先恢复摄像头枚举，再确认格式、帧率和时间戳；之后才运行原始程序。

