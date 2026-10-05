import cv2
import time
import math
import numpy as np
import threading
import subprocess
import json
from flask import Flask, Response, jsonify
from adafruit_servokit import ServoKit
from ultralytics import YOLO

# ================= 🔧 核心配置 =================
AI_INTERVAL = 3        
# 🌟 稍微调低推流 JPEG 质量以保证 WiFi 下的流畅度
# 1080P 的数据量很大，如果 WiFi 信号不好，设为 50-60，如果信号好，设为 70-80
JPEG_QUALITY = 60 

# 🌟 分辨率解耦配置 🌟
# AI 依然跑在低分下以保证速度和逻辑兼容
AI_WIDTH, AI_HEIGHT = 480, 270 #保持16：9
AI_AREA = AI_WIDTH * AI_HEIGHT

# 推流使用高清分辨率 (720P 是 RPi5 软编的最佳平衡点)
STREAM_WIDTH, STREAM_HEIGHT = 1920, 1080

PAN_CHANNEL = 1
TILT_CHANNEL = 0
INVERT_PAN = True    
INVERT_TILT = False   
PAN_OFFSET = 90  
TILT_OFFSET = 90  
PAN_LIMIT = (-90, 90)   
TILT_LIMIT = (-90, 90) 

START_PAN = 0.0
START_TILT = -90.0 
COMPOSITION_SINGLE = 0.33 
COMPOSITION_DOUBLE = 0.5  
SMOOTH_FACTOR = 0.25   
MIN_SERVO_STEP = 0.5   
DEAD_ZONE = 15         

SHOWCASE_TRIGGER_TIME = 2.0  
ZOOM_LEVEL = 2.2             
ZOOM_SPEED = 0.08            
SHOWCASE_OFFSET_Y = 60

AUTO_PATROL_TIME = 5.0 
SEARCH_SPEED = 1.0     
SEARCH_W_AMP = 60
SEARCH_H_AMP = 20
MIN_TARGET_AREA = 0.03 
AUTO_PRIVACY_TIME = 30.0

# ===================================================

app = Flask(__name__)
try:
    kit = ServoKit(channels=16)
except:
    kit = None

# 全局数据
GLOBAL_STATS = {
    'fps': 0,
    'cpu': 0,
    'mode': 'INIT',     
    'targets': 0,
    'zoom': 1.0,
    'gesture': 'NONE',  
    'log': "System Booting..."
}

# ================= 🚀 摄像头终极优化 (多线程 + MJPEG) =================
class CameraStream:
    def __init__(self, src=0, width=1920, height=1080):
        # 1. 开启摄像头
        self.stream = cv2.VideoCapture(src)
        
        # 🌟 关键设置：强制使用 MJPEG 格式 🌟
        # C920 内置硬件压缩，必须开启这个才能在 1080P 下跑满 30FPS
        self.stream.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        
        # 2. 设置 1080P 分辨率
        self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.stream.set(cv2.CAP_PROP_FPS, 30)
        
        # 3. 缓冲区设置为 1，确保永远读取最新帧，减少延迟
        self.stream.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        (self.grabbed, self.frame) = self.stream.read()
        self.started = False
        self.read_lock = threading.Lock()

    def start(self):
        if self.started:
            print("📷 摄像头线程已在运行")
            return None
        self.started = True
        self.thread = threading.Thread(target=self.update, args=())
        self.thread.daemon = True # 设置为守护线程，主程序退出时自动结束
        self.thread.start()
        print(f"✅ 摄像头启动: 1080P MJPEG 模式 (线程 ID: {self.thread.ident})")
        return self

    def update(self):
        while self.started:
            if not self.stream.isOpened():
                time.sleep(0.1)
                continue
            
            # 只抓取，不解码 (grab 只有 read 的 1/10 耗时)
            grabbed = self.stream.grab() 
            
            if grabbed:
                # 只有当需要帧的时候才 retrieve (解码)
                # 这里为了简化，我们还是直接 read，但在 Pi5 上 MJPEG 解码极快
                (ret, frame) = self.stream.retrieve()
                if ret:
                    with self.read_lock:
                        # 翻转（如果在云台上倒装）
                        self.frame = cv2.flip(frame, 1) 
            else:
                time.sleep(0.01)

    def read(self):
        with self.read_lock:
            if self.frame is not None:
                return self.frame.copy() # 返回副本，防止处理时被新帧覆盖产生撕裂
        return None

    def stop(self):
        self.started = False
        self.thread.join()
        self.stream.release()

# 初始化全局摄像头流 (1080P)
# 注意：配置必须与上面 Class 定义一致
STREAM_WIDTH, STREAM_HEIGHT = 1920, 1080
video_stream = CameraStream(src=0, width=STREAM_WIDTH, height=STREAM_HEIGHT).start()
time.sleep(2.0) # 等待摄像头预热和自动对焦/白平衡稳定

def get_cpu_temperature():
    try:
        output = subprocess.check_output(['vcgencmd', 'measure_temp']).decode('utf-8')
        return float(output.replace('temp=', '').replace('\'C\n', ''))
    except: return 0.0

def safe_move_servo(channel, logical_angle):
    if kit is None: return
    try:
        physical_angle = 0
        if channel == PAN_CHANNEL: physical_angle = logical_angle + PAN_OFFSET
        elif channel == TILT_CHANNEL: physical_angle = logical_angle + TILT_OFFSET
        physical_angle = max(0, min(180, physical_angle))
        kit.servo[channel].angle = physical_angle
    except: pass

# 初始化
real_pan = START_PAN
real_tilt = START_TILT
safe_move_servo(PAN_CHANNEL, real_pan)
safe_move_servo(TILT_CHANNEL, real_tilt)

try:
    print("🚀 加载 AI 模型...")
    model = YOLO("yolov8n-pose_ncnn_model")
except:
    print("⚠️ 使用普通模型...")
    model = YOLO("yolov8n-pose.pt")

# 🌟 这里的 WIDTH/HEIGHT 依然保留给 AI 逻辑使用，对应 320x240
WIDTH, HEIGHT = AI_WIDTH, AI_HEIGHT
SCREEN_AREA = AI_AREA

# 状态变量
state_mode = "SEARCHING"
last_human_time = time.time()
showcase_timer_start = 0
current_zoom = 1.0
zoom_center_x, zoom_center_y = WIDTH//2, HEIGHT//2

def update_log(msg):
    if GLOBAL_STATS['log'] != msg:
        GLOBAL_STATS['log'] = msg

def smooth_move_servos(target_x, target_y, composition_ratio, is_showcase=False):
    global real_pan, real_tilt
    # 逻辑依然基于 AI_WIDTH (320) 计算，无需修改 PID 参数
    target_ref_y = int(HEIGHT * composition_ratio)
    ref_x = WIDTH // 2
    error_x = ref_x - target_x
    error_y = target_ref_y - target_y 
    
    if abs(error_x) < DEAD_ZONE: error_x = 0
    if abs(error_y) < DEAD_ZONE: error_y = 0
    
    kp = 0.06 if is_showcase else 0.1 
    change_pan = error_x * kp if not INVERT_PAN else -error_x * kp
    change_tilt = -error_y * 0.05 if not INVERT_TILT else error_y * 0.05 
    
    ideal_pan = max(PAN_LIMIT[0], min(PAN_LIMIT[1], real_pan + change_pan))
    ideal_tilt = max(TILT_LIMIT[0], min(TILT_LIMIT[1], real_tilt + change_tilt))

    next_pan = (real_pan * (1 - SMOOTH_FACTOR)) + (ideal_pan * SMOOTH_FACTOR)
    next_tilt = (real_tilt * (1 - SMOOTH_FACTOR)) + (ideal_tilt * SMOOTH_FACTOR)
    
    if abs(next_pan - real_pan) > MIN_SERVO_STEP:
        real_pan = next_pan
        safe_move_servo(PAN_CHANNEL, real_pan)
    if abs(next_tilt - real_tilt) > MIN_SERVO_STEP:
        real_tilt = next_tilt
        safe_move_servo(TILT_CHANNEL, real_tilt)

def perform_search():
    global real_pan, real_tilt
    t = time.time() * SEARCH_SPEED
    new_pan = START_PAN + math.cos(t) * SEARCH_W_AMP
    new_tilt = START_TILT + abs(math.sin(t * 2)) * SEARCH_H_AMP 
    real_pan = max(PAN_LIMIT[0], min(PAN_LIMIT[1], new_pan))
    real_tilt = max(TILT_LIMIT[0], min(TILT_LIMIT[1], new_tilt))
    safe_move_servo(PAN_CHANNEL, real_pan)
    safe_move_servo(TILT_CHANNEL, real_tilt)

def check_showcase_pose(keypoints):
    try:
        nose_y = keypoints[0][1]
        l_wrist = keypoints[9]
        r_wrist = keypoints[10]
        hands_close = math.hypot(l_wrist[0]-r_wrist[0], l_wrist[1]-r_wrist[1]) < 60
        hands_level = (l_wrist[1] > nose_y) and (l_wrist[1] < 240) and (l_wrist[1] > 0)
        return hands_close and hands_level
    except: return False

def detect_gestures(keypoints):
    try:
        nose_y = keypoints[0][1]
        l_eye_y = keypoints[1][1]
        l_wrist = keypoints[9]
        r_wrist = keypoints[10]
        
        if l_wrist[1] < nose_y and r_wrist[1] < nose_y and l_wrist[1]>0: return "BOTH_HANDS_UP"
        if l_wrist[1] < l_eye_y and l_wrist[1] > 0: return "LEFT_HAND_UP"
    except: pass
    return None

def digital_zoom(frame, center_x, center_y, scale):
    if scale <= 1.01: return frame
    h, w = frame.shape[:2]
    new_w, new_h = int(w/scale), int(h/scale)
    x1 = max(0, min(center_x - new_w//2, w - new_w))
    y1 = max(0, min(center_y - new_h//2, h - new_h))
    crop = frame[y1:y1+new_h, x1:x1+new_w]
    return cv2.resize(crop, (w, h), interpolation=cv2.INTER_LINEAR)

def generate_frames():
    global state_mode, last_human_time, showcase_timer_start, current_zoom, zoom_center_x, zoom_center_y
    frame_count = 0
    prev_time = time.time()
    
    while True:
        # 1. 获取高清帧 (1280x720)
        high_res_frame = video_stream.read()
        if high_res_frame is None:
            time.sleep(0.005)
            continue
        
        # 2. 生成低清帧给 AI (320x240) - 提高处理速度
        ai_frame = cv2.resize(high_res_frame, (AI_WIDTH, AI_HEIGHT))

        curr_time = time.time()
        time_delta = curr_time - prev_time
        if time_delta > 0:
            fps = 1 / time_delta
            GLOBAL_STATS['fps'] = int(GLOBAL_STATS['fps'] * 0.9 + fps * 0.1)
        prev_time = curr_time
        
        if frame_count % 30 == 0:
            GLOBAL_STATS['cpu'] = get_cpu_temperature()

        GLOBAL_STATS['mode'] = state_mode
        GLOBAL_STATS['zoom'] = round(current_zoom, 1)
        frame_count += 1
        
        should_run_ai = (frame_count % AI_INTERVAL == 0)
        
        if should_run_ai:
            # 🌟 AI 跑在小图上
            results = model(ai_frame, verbose=False, conf=0.5)
            temp_kpts = []
            
            if results[0].boxes is not None and len(results[0].boxes) > 0:
                boxes = results[0].boxes.xywh.cpu().numpy()
                kpts_data = results[0].keypoints.xy.cpu().numpy()
                valid_targets = []
                for i, box in enumerate(boxes):
                    # 面积判断依然基于 AI_WIDTH/AI_HEIGHT 的比例
                    area_ratio = (box[2] * box[3]) / SCREEN_AREA
                    if area_ratio >= MIN_TARGET_AREA:
                        valid_targets.append({'area': box[2]*box[3], 'kpts': kpts_data[i]})
                
                valid_targets.sort(key=lambda x: x['area'], reverse=True)
                temp_kpts = [t['kpts'] for t in valid_targets[:2]]
                
                if len(temp_kpts) > 0:
                    last_human_time = time.time()
                    if state_mode in ["SEARCHING", "PRIVACY"]: 
                        state_mode = "TRACKING"
                        update_log("Target Acquired.")
            
            GLOBAL_STATS['targets'] = len(temp_kpts)
            
            # --- 逻辑 (依然使用 ai_frame 的坐标 0-320) ---
            display_gesture = "NONE"

            if state_mode == "TRACKING" and len(temp_kpts) > 0:
                # 1. 带货检测
                if check_showcase_pose(temp_kpts[0]):
                    display_gesture = "📦 HOLDING"
                    if showcase_timer_start == 0: 
                        showcase_timer_start = time.time()
                    elif time.time() - showcase_timer_start > SHOWCASE_TRIGGER_TIME:
                        state_mode = "SHOWCASE"
                        showcase_timer_start = 0
                        update_log(">> SHOWCASE MODE <<")
                else:
                    showcase_timer_start = 0 
                
                # 2. 手势检测
                if state_mode != "SHOWCASE":
                    gesture = detect_gestures(temp_kpts[0])
                    if gesture: 
                        display_gesture = gesture
                        if gesture == "BOTH_HANDS_UP":
                            update_log("Gesture: RESET")
                            real_pan, real_tilt = START_PAN, START_TILT
                            safe_move_servo(PAN_CHANNEL, real_pan); safe_move_servo(TILT_CHANNEL, real_tilt)
                        elif gesture == "LEFT_HAND_UP":
                            state_mode = "LOCKED"
                            update_log("Gesture: LOCK")

                # 3. 舵机追踪 (计算误差传给PID)
                if len(temp_kpts) == 1:
                    kpts = temp_kpts[0]
                    l_eye, r_eye, nose = kpts[1], kpts[2], kpts[0]
                    if l_eye[0]>0 and r_eye[0]>0: tx, ty = (l_eye[0]+r_eye[0])/2, (l_eye[1]+r_eye[1])/2
                    else: tx, ty = nose[0], nose[1]
                    ratio = COMPOSITION_SINGLE
                else:
                    ratio = COMPOSITION_DOUBLE
                    sx = sum([k[0][0] for k in temp_kpts]) / len(temp_kpts)
                    sy = sum([k[0][1] for k in temp_kpts]) / len(temp_kpts)
                    tx, ty = sx, sy
                
                zoom_center_x, zoom_center_y = int(tx), int(ty)
                smooth_move_servos(tx, ty, ratio)

            elif state_mode == "SHOWCASE" and len(temp_kpts) > 0:
                display_gesture = "📦 SHOWCASE"
                kpts = temp_kpts[0]
                if check_showcase_pose(kpts):
                    l_w, r_w = kpts[9], kpts[10]
                    hcx, hcy = (l_w[0]+r_w[0])/2, (l_w[1]+r_w[1])/2
                    obj_y = hcy - SHOWCASE_OFFSET_Y
                    zoom_center_x, zoom_center_y = int(hcx), int(obj_y)
                    smooth_move_servos(hcx, obj_y, 0.5, is_showcase=True)
                else: 
                    state_mode = "TRACKING"
                    update_log("Showcase Ended.")

            elif state_mode == "LOCKED":
                display_gesture = "🔒 LOCKED"
                if len(temp_kpts) > 0:
                    gesture = detect_gestures(temp_kpts[0])
                    if gesture == "LEFT_HAND_UP":
                        state_mode = "TRACKING"
                        update_log("System Unlocked.")

            elif state_mode == "SEARCHING":
                perform_search()
            elif state_mode == "PRIVACY":
                safe_move_servo(PAN_CHANNEL, 0); safe_move_servo(TILT_CHANNEL, 80)

            GLOBAL_STATS['gesture'] = display_gesture

        # 超时逻辑
        if state_mode != "LOCKED" and state_mode != "SHOWCASE":
            t_diff = time.time() - last_human_time
            if t_diff > AUTO_PRIVACY_TIME: 
                if state_mode != "PRIVACY": update_log("Sleep Mode."); state_mode = "PRIVACY"
            elif t_diff > AUTO_PATROL_TIME: 
                if state_mode != "SEARCHING": update_log("Searching..."); state_mode = "SEARCHING"

        # 3. 变焦与渲染 (关键步骤)
        target_zoom = ZOOM_LEVEL if state_mode == "SHOWCASE" else 1.0
        current_zoom += (target_zoom - current_zoom) * ZOOM_SPEED
        
        # 🌟 坐标映射：将 AI 的小图坐标 (320x240) 映射回 高清大图 (1280x720)
        # 这样 digital_zoom 切割的就是高清图的像素，实现无损变焦
        scale_x = STREAM_WIDTH / AI_WIDTH
        scale_y = STREAM_HEIGHT / AI_HEIGHT
        
        hd_center_x = int(zoom_center_x * scale_x)
        hd_center_y = int(zoom_center_y * scale_y)
        
        # 对高清图进行裁切变焦
        display_frame = digital_zoom(high_res_frame, hd_center_x, hd_center_y, current_zoom)

        # 4. UI 绘制 (适配高清坐标系)
        # 获取当前显示帧的尺寸 (可能是变焦后的尺寸，通常resize回原尺寸，但这里digital_zoom返回的是原尺寸)
        disp_h, disp_w = display_frame.shape[:2]

        if showcase_timer_start > 0:
            prog = (time.time() - showcase_timer_start) / SHOWCASE_TRIGGER_TIME
            w_bar = int(disp_w * prog) # 动态宽度
            # 动态底部坐标 (底部向上5像素)
            bar_y = disp_h - 5 
            cv2.rectangle(display_frame, (0, bar_y-5), (w_bar, bar_y), (0, 255, 255), -1)

        if state_mode == "SHOWCASE":
            # 动态居中
            cx, cy = disp_w // 2, disp_h // 2
            box_size = int(100 * (disp_w / 640)) # 根据画面大小缩放框的大小
            cv2.rectangle(display_frame, (cx-box_size, cy-box_size), (cx+box_size, cy+box_size), (0, 255, 255), 2)
            cv2.putText(display_frame, "PRODUCT FOCUS", (cx-box_size-10, cy-box_size-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255), 2)

        # 推流编码 (使用较高质量)
        ret, buffer = cv2.imencode('.jpg', display_frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/stats')
def stats(): return jsonify(GLOBAL_STATS)

@app.route('/video_feed')
def video_feed(): return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>AI Director Pro</title>
    <style>
        body { background: #111; color: #0f0; font-family: 'Courier New', monospace; margin: 0; display: flex; height: 100vh; overflow: hidden; }
        
        .viewport { flex: 3; position: relative; background: #000; border-right: 2px solid #333; display: flex; align-items: center; justify-content: center; }
        .viewport img { width: 100%; max-height: 100%; object-fit: contain; }
        
        .overlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }
        .corner { position: absolute; width: 30px; height: 30px; border: 3px solid #0f0; }
        .tl { top: 20px; left: 20px; border-right: 0; border-bottom: 0; }
        .tr { top: 20px; right: 20px; border-left: 0; border-bottom: 0; }
        .bl { bottom: 20px; left: 20px; border-right: 0; border-top: 0; }
        .br { bottom: 20px; right: 20px; border-left: 0; border-top: 0; }
        
        .rec-tag { position: absolute; top: 30px; right: 40px; color: red; font-weight: bold; animation: blink 1s infinite; display: none; }
        .rec-tag.active { display: block; }
        @keyframes blink { 50% { opacity: 0; } }

        .sidebar { flex: 1; background: #1a1a1a; padding: 20px; display: flex; flex-direction: column; gap: 20px; box-shadow: -5px 0 15px rgba(0,0,0,0.5); }
        .panel { background: #222; border: 1px solid #444; padding: 15px; border-radius: 5px; }
        .panel-title { margin: 0 0 10px 0; color: #0ff; font-size: 14px; border-bottom: 1px solid #444; padding-bottom: 5px; }
        
        .stat-row { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 16px; }
        .val { font-weight: bold; color: #fff; }
        .bar-box { width: 100%; height: 8px; background: #333; border-radius: 4px; overflow: hidden; }
        .bar-fill { height: 100%; background: #0f0; width: 0%; transition: width 0.5s; }
        
        .gesture-box { 
            background: #002200; border: 2px solid #00ff41; color: #00ff41; 
            padding: 20px; text-align: center; font-size: 24px; font-weight: bold;
            border-radius: 8px; text-shadow: 0 0 10px #00ff41;
            transition: all 0.3s;
        }
        .gesture-box.active { background: #004400; transform: scale(1.05); }

        .console { flex-grow: 1; background: #000; border: 1px solid #333; padding: 10px; overflow-y: auto; font-size: 12px; color: #888; height: 150px; }
        .log-entry { margin-bottom: 4px; border-bottom: 1px dashed #222; }
        .log-time { color: #005500; margin-right: 5px; }
        
    </style>
</head>
<body>

    <div class="viewport">
        <img src="/video_feed">
        <div class="overlay">
            <div class="corner tl"></div><div class="corner tr"></div>
            <div class="corner bl"></div><div class="corner br"></div>
            <div class="rec-tag" id="rec-icon">● LIVE 720P</div>
            <div style="position:absolute; bottom:30px; left:50%; transform:translateX(-50%); color:#0ff; font-size:12px;">AI TRACKING SYSTEM V5.1 (HD)</div>
        </div>
    </div>

    <div class="sidebar">
        <div class="panel">
            <div class="panel-title">SYSTEM STATUS</div>
            <div class="stat-row"><span>TASK</span> <span id="mode" class="val" style="color:yellow">INIT</span></div>
            <div class="stat-row"><span>TEMP</span> <span id="temp" class="val">0°C</span></div>
            <div class="stat-row"><span>FPS</span> <span id="fps" class="val">0</span></div>
            <div class="stat-row"><span>TARGETS</span> <span id="targets" class="val">0</span></div>
        </div>

        <div class="panel">
            <div class="panel-title">ZOOM LEVEL</div>
            <div class="stat-row"><span>MAGNIFICATION</span> <span id="zoom-val" class="val">1.0x</span></div>
            <div class="bar-box"><div id="zoom-bar" class="bar-fill" style="width: 0%"></div></div>
        </div>

        <div class="panel">
            <div class="panel-title">LIVE POSTURE</div>
            <div id="gesture-display" class="gesture-box">Scanning...</div>
        </div>

        <div class="console" id="sys-log">
            <div class="log-entry">System Initialized (HD Engine)...</div>
        </div>
    </div>

    <script>
        function log(msg) {
            const box = document.getElementById('sys-log');
            const line = document.createElement('div');
            line.className = 'log-entry';
            const time = new Date().toLocaleTimeString();
            line.innerHTML = `<span class="log-time">[${time}]</span> ${msg}`;
            box.appendChild(line);
            box.scrollTop = box.scrollHeight;
        }

        let lastLog = "";

        setInterval(() => {
            fetch('/stats').then(r => r.json()).then(d => {
                document.getElementById('fps').innerText = d.fps;
                document.getElementById('mode').innerText = d.mode;
                document.getElementById('targets').innerText = d.targets;
                document.getElementById('zoom-val').innerText = d.zoom + "x";
                document.getElementById('temp').innerText = d.cpu + "°C";
                
                let pct = (d.zoom - 1.0) * 100;
                document.getElementById('zoom-bar').style.width = pct + "%";

                const rec = document.getElementById('rec-icon');
                if (d.mode === 'TRACKING' || d.mode === 'SHOWCASE') rec.classList.add('active');
                else rec.classList.remove('active');

                const gBox = document.getElementById('gesture-display');
                if (d.gesture && d.gesture !== 'NONE') {
                    gBox.innerText = d.gesture;
                    gBox.classList.add('active');
                    gBox.style.color = '#00ffff';
                    gBox.style.borderColor = '#00ffff';
                } else {
                    gBox.innerText = "NO GESTURE";
                    gBox.classList.remove('active');
                    gBox.style.color = '#004400';
                    gBox.style.borderColor = '#004400';
                }

                if (d.log && d.log !== lastLog) {
                    log(d.log);
                    lastLog = d.log;
                }
            });
        }, 500);
    </script>
</body>
</html>
    """

if __name__ == '__main__':
    # 启用多线程模式以应对高清流的并发请求
    app.run(host='redacted', port=5000, debug=False, threaded=True)