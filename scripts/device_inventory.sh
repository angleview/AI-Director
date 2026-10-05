#!/usr/bin/env sh

set -u
export LC_ALL=C

section() {
    printf '\n[%s]\n' "$1"
}

run_if_available() {
    command_name="$1"
    shift
    if command -v "$command_name" >/dev/null 2>&1; then
        "$command_name" "$@" 2>&1 || true
    else
        printf '%s\n' "$command_name: not installed"
    fi
}

section identity
printf 'captured_at=%s\n' "$(date --iso-8601=seconds 2>/dev/null || date)"
printf 'kernel=%s\n' "$(uname -r)"
printf 'architecture=%s\n' "$(uname -m)"
if [ -r /proc/device-tree/model ]; then
    printf 'device_model='
    tr -d '\000' < /proc/device-tree/model
    printf '\n'
fi
if [ -r /etc/os-release ]; then
    . /etc/os-release
    printf 'os=%s\n' "${PRETTY_NAME:-unknown}"
fi

section cpu
run_if_available lscpu
printf 'online_cpus=%s\n' "$(getconf _NPROCESSORS_ONLN 2>/dev/null || printf unknown)"
for cpu_path in /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq \
                /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq; do
    if [ -r "$cpu_path" ]; then
        printf '%s=%s\n' "$(basename "$cpu_path")" "$(cat "$cpu_path")"
    fi
done

section memory
run_if_available free -b

section storage
run_if_available df -B1 /

section runtime_state
run_if_available uptime
if command -v vcgencmd >/dev/null 2>&1; then
    vcgencmd measure_temp 2>&1 || true
    vcgencmd get_throttled 2>&1 || true
    vcgencmd measure_clock arm 2>&1 || true
else
    printf 'vcgencmd: not installed\n'
fi
if [ -r /sys/class/thermal/thermal_zone0/temp ]; then
    printf 'thermal_zone0_millicelsius=%s\n' "$(cat /sys/class/thermal/thermal_zone0/temp)"
fi

section video_devices
run_if_available lsusb
video_found=false
for device_path in /dev/video* /dev/media*; do
    if [ -e "$device_path" ]; then
        video_found=true
        ls -l "$device_path"
    fi
done
if [ "$video_found" = false ]; then
    printf 'none\n'
fi
if command -v v4l2-ctl >/dev/null 2>&1; then
    v4l2-ctl --list-devices 2>&1 || true
    if [ -e /dev/video0 ]; then
        v4l2-ctl --device /dev/video0 --get-fmt-video 2>&1 || true
        v4l2-ctl --device /dev/video0 --get-parm 2>&1 || true
        v4l2-ctl --device /dev/video0 --list-formats-ext 2>&1 || true
    fi
else
    printf 'v4l2-ctl: not installed\n'
fi
if command -v rpicam-hello >/dev/null 2>&1; then
    rpicam-hello --list-cameras 2>&1 || true
elif command -v libcamera-hello >/dev/null 2>&1; then
    libcamera-hello --list-cameras 2>&1 || true
else
    printf 'rpicam/libcamera camera tools: not installed\n'
fi

section hardware_interfaces
i2c_found=false
for device_path in /dev/i2c*; do
    if [ -e "$device_path" ]; then
        i2c_found=true
        ls -l "$device_path"
    fi
done
if [ "$i2c_found" = false ]; then
    printf 'i2c_devices=none\n'
fi
run_if_available i2cdetect -l


section python
run_if_available python3 --version
run_if_available python3 -m pip --version
if command -v python3 >/dev/null 2>&1; then
    python3 - <<'PY'
from importlib import metadata, util

packages = {
    "cv2": "opencv-python",
    "numpy": "numpy",
    "flask": "flask",
    "ultralytics": "ultralytics",
    "adafruit_servokit": "adafruit-circuitpython-servokit",
    "ncnn": "ncnn",
    "torch": "torch",
}

for module_name, distribution_name in packages.items():
    available = util.find_spec(module_name) is not None
    try:
        version = metadata.version(distribution_name)
    except metadata.PackageNotFoundError:
        version = "not-installed"
    print(f"{module_name}: available={str(available).lower()} version={version}")
PY
fi

