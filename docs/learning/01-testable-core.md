> 历史学习记录；当前可运行命令、完整模型与素材获取见 [部署说明](../deployment.md)。

# 第一课：先建立可测试的同步核心

## 学习目标

这一阶段只回答一个问题：一帧输入如何确定地变成一次推理结果、一个运行模式和一个控制意图？暂时不引入线程、摄像头、NCNN 或网页，避免并发和外部依赖掩盖核心逻辑。

## 阅读顺序

1. `src/edge_ai_director/domain.py`：先理解系统交换的数据，而不是库对象。
2. `src/edge_ai_director/interfaces.py`：理解 Protocol 如何划分依赖边界。
3. `src/edge_ai_director/state_machine.py`：理解手势边沿、超时和模式转换。
4. `src/edge_ai_director/control.py`：理解归一化坐标如何消除分辨率耦合。
5. `src/edge_ai_director/simulated.py`：理解回放源与虚拟执行器不是“假功能”，而是确定性验证工具。
6. `src/edge_ai_director/pipeline.py`：最后串起完整同步调用链。

## 调用链

```text
ReplayFrameSource.read()
  -> InferenceBackend.infer(frame)
  -> DirectorStateMachine.update(perception)
  -> CompositionController.plan(perception, decision)
  -> VirtualActuator.apply(intent)
  -> PipelineResult + StageTimings
```

每个阶段只接收显式输入并返回显式输出。`Frame.sequence` 将推理结果、控制意图和执行记录关联起来；如果序号不一致，流水线立即报错，而不是把错帧控制当成正常结果。

## 运行

PowerShell：

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
python -m edge_ai_director.demo
```

Linux / Raspberry Pi：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m edge_ai_director.demo
```

演示输出中，持续举起左手只产生一次边沿事件，因此系统进入 `LOCKED` 后不会在下一帧立即解锁；手势先释放、再举起时才产生新的解锁事件。

## 验证记录

2026-08-06，本机与 Raspberry Pi 5（Python 3.13.5）均通过同一组 6 个单元测试，模拟演示输出一致。树莓派使用隔离目录 `.`，没有安装新依赖或访问外设。

演示中的 `total_ms=4.0` 来自每次固定前进 1 ms 的虚拟时钟，只用于证明各阶段计时和汇总关系正确，不是树莓派性能数据。真实延迟必须在接入 OpenCV 与 NCNN 后使用单调时钟重新测量。

## 这一阶段修复的原型问题

- 模块导入不再自动打开硬件。
- 运行模式从全局字符串变成显式状态机。
- 持续手势从“每帧命令”变成“边沿事件”。
- 控制使用 0–1 归一化坐标，不再依赖 320、480 或 640 像素阈值。
- 控制意图与物理动作分离，仿真结果不会被误写成舵机性能。
- 每个阶段已有独立计时边界，为后续真实性能测量做准备。

## 你应当能解释

1. 为什么先写同步参考实现，再加入多线程？
2. `Protocol` 与直接依赖 OpenCV/ServoKit 类有什么区别？
3. 为什么 `Frame` 和 `Perception` 必须携带同一个序号？
4. 为什么持续为真的手势条件不能直接作为切换命令？
5. 为什么归一化坐标比固定像素阈值更适合多分辨率部署？
6. 虚拟执行器与简单的空函数有什么本质区别？

## 动手练习

先不要修改主程序。完成以下练习并重新运行测试：

1. 为 `VirtualActuator` 增加“最大单次角度变化”限制，并编写边界测试。
2. 增加右手手势，但先写出它的领域含义和状态迁移再编码。
3. 构造一个推理结果帧号错误的测试，观察流水线在哪里阻止错帧控制。

下一课会用视频文件替换脚本化输入，并加入真实的 OpenCV 预处理和 NCNN 适配边界。
