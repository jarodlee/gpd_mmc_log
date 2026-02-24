#!/usr/bin/env python3
import json
import time
import os
import subprocess
import datetime
import re

TBW_LIMIT_TB = 80
ALERT_GB_PER_DAY = 30
BATTERY_ALERT_LEVEL = 20

#STATE_FILE = "/var/log/mmc_state.json" no perimer error
#STATE_FILE = "/tmp/mmc_state.json" tmp test is ok

STATE_FILE = "/var/www/mmc/mmc_state.json"

# ========= 写入统计（重构为持久化模型） =========

def get_current_sector():
    with open("/proc/diskstats") as f:
        for line in f:
            if "mmcblk0 " in line:
                return int(line.split()[9])  # 写扇区
    return 0

def update_write_stats():
    current_sector = get_current_sector()
    today = str(datetime.date.today())

    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            state = json.load(f)
    else:
        state = {
            "last_sector": current_sector,
            "total_sector": 0,
            "daily_sector": 0,
            "last_day": today,
            "first_ts": int(time.time())
        }

    delta = current_sector - state["last_sector"]

    # 处理重启导致计数器回退
    if delta < 0:
        delta = current_sector

    state["total_sector"] += delta

    # 跨天重置 daily
    if state["last_day"] != today:
        state["daily_sector"] = 0
        state["last_day"] = today

    state["daily_sector"] += delta
    state["last_sector"] = current_sector

    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

    return state

state = update_write_stats()

today_gb = state["daily_sector"] * 512 / (1024**3)
total_tb = state["total_sector"] * 512 / (1024**4)

total_days = max((int(time.time()) - state["first_ts"]) / 86400, 1)
avg_daily_gb = (state["total_sector"] * 512 / (1024**3)) / total_days

life_used_percent = (total_tb / TBW_LIMIT_TB) * 100
remaining_tb = TBW_LIMIT_TB - total_tb
remaining_years = None

if total_days >= 3 and avg_daily_gb > 0:
    remaining_days = (remaining_tb * 1024) / avg_daily_gb
    remaining_years = remaining_days / 365

alert = today_gb > ALERT_GB_PER_DAY

history = []  # 单机稳定版不再依赖历史日志

# ========= EXT_CSD 寿命读取 =========

def read_emmc_health():
    try:
        out = subprocess.check_output(
            ["mmc", "extcsd", "read", "/dev/mmcblk0"],
            stderr=subprocess.DEVNULL
        ).decode()

        life_a = None
        pre_eol = None

        for line in out.splitlines():
            if "Life Time Estimation A" in line:
                life_a = int(re.search(r'0x([0-9A-Fa-f]+)', line).group(1), 16)
            if "Pre EOL information" in line:
                pre_eol = int(re.search(r'0x([0-9A-Fa-f]+)', line).group(1), 16)

        return life_a, pre_eol

    except:
        return None, None

emmc_life_a, emmc_pre_eol = read_emmc_health()

# ========= 电池 =========
battery_percent = None
battery_status = None
battery_alert = False

for p in os.listdir("/sys/class/power_supply"):
    path = f"/sys/class/power_supply/{p}"
    if "battery" in p.lower():
        try:
            with open(path + "/capacity") as f:
                battery_percent = int(f.read().strip())
            with open(path + "/status") as f:
                battery_status = f.read().strip()
            if battery_percent is not None and battery_percent < BATTERY_ALERT_LEVEL:
                battery_alert = True
            break
        except:
            pass

# ========= 温度 =========
temperature_c = None
try:
    for zone in os.listdir("/sys/class/thermal"):
        zpath = f"/sys/class/thermal/{zone}"
        if zone.startswith("thermal_zone"):
            with open(zpath + "/temp") as f:
                temp = int(f.read().strip())
                if 1000 < temp < 120000:
                    temperature_c = round(temp / 1000, 1)
                    break
except:
    pass

# ========= WiFi IP =========
wifi_ip = None
try:
    output = subprocess.check_output(
        "ip -4 addr | grep -E 'wlp|wlan' -A2 | grep inet",
        shell=True
    ).decode()

    for line in output.splitlines():
        if "inet" in line:
            wifi_ip = line.strip().split()[1].split("/")[0]
            break
except:
    pass

# ========= CPU =========
cpu_usage = None
try:
    def read_cpu():
        with open("/proc/stat") as f:
            line = f.readline()
            parts = list(map(int, line.strip().split()[1:]))
            idle = parts[3]
            total = sum(parts)
            return idle, total

    idle1, total1 = read_cpu()
    time.sleep(0.1)
    idle2, total2 = read_cpu()

    idle_delta = idle2 - idle1
    total_delta = total2 - total1

    cpu_usage = round(100 * (1 - idle_delta / total_delta), 1)
except:
    pass

# ========= 内存 =========
mem_used_percent = None
try:
    mem = subprocess.check_output("free", shell=True).decode().splitlines()[1].split()
    total_mem = int(mem[1])
    used_mem = int(mem[2])
    mem_used_percent = round((used_mem / total_mem) * 100, 1)
except:
    pass

# ========= ZFS ARC =========
arc_size_gb = None
try:
    with open("/proc/spl/kstat/zfs/arcstats") as f:
        for line in f:
            if line.startswith("size"):
                arc_bytes = int(line.split()[2])
                arc_size_gb = round(arc_bytes / (1024**3), 2)
                break
except:
    pass

result = {
    "history": history,
    "total_tb": round(total_tb, 2),
    "today_gb": round(today_gb, 2),
    "avg_daily_gb": round(avg_daily_gb, 2),
    "life_used_percent": round(life_used_percent, 2),
    "remaining_years": round(remaining_years, 2) if remaining_years else None,
    "emmc_life_level": emmc_life_a,
    "emmc_pre_eol": emmc_pre_eol,
    "battery_percent": battery_percent,
    "battery_status": battery_status,
    "battery_alert": battery_alert,
    "temperature_c": temperature_c,
    "wifi_ip": wifi_ip,
    "cpu_usage": cpu_usage,
    "mem_used_percent": mem_used_percent,
    "arc_size_gb": arc_size_gb,
    "alert": alert
}

print("Content-Type: application/json\n")
print(json.dumps(result))
