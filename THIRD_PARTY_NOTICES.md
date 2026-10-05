# 第三方来源与授权

## YOLOv8n Pose 模型与 Ultralytics

模型源自 [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics)，不是本项目自主训练模型。上游提供 AGPL-3.0 与其他授权选项；本次发布按上游 AGPL-3.0 模型来源记录。模型对应输入权重及导出文件 SHA-256 见 assets/models/manifest.json。上游代码与许可证：[Ultralytics LICENSE](https://github.com/ultralytics/ultralytics/blob/main/LICENSE)。

随附 [AGPL-3.0 许可证全文](licenses/Ultralytics-AGPL-3.0.txt)，取自上游 v8.3.225。对应版本源代码可从 [Ultralytics v8.3.225](https://github.com/ultralytics/ultralytics/tree/v8.3.225) 获取。

随模型发布的 metadata.yaml、model_ncnn.py 是上游导出产物。model_ncnn.py 不是标准部署入口，也不应作为自行编写的模型转换器陈述。

## 公共图片

bus.jpg 从 Ultralytics 公共地址获取，来源、许可链接和校验值保存在 assets/inputs/manifest.json。回放是该图片生成的静态视频。图片与生成视频不直接提交至 Git；下载仍需遵守其上游授权。

## NCNN 及其他库

[NCNN](https://github.com/Tencent/ncnn) 的来源和许可证见其官方仓库。本项目通过 Python 包使用 NCNN、OpenCV、NumPy、PyTorch、torchvision；没有把这些库的实现归为个人贡献。

以上说明只描述第三方资产来源，不为项目原创代码添加新的授权，也不改变各上游许可证。需要使用或分发第三方组件时，以对应版本许可证为准。
