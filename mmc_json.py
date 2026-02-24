#!/usr/bin/env python3
import json
import time
import os
import subprocess

TBW_LIMIT_TB = 80
ALERT_GB_PER_DAY = 30

# ========= 写入日志 =========
with open("/var/log/mmc_stat.log") as f:
    lines = f.readlines()

if len(lines) < 2:
    print("Content-Type: application/json\n")
    print(json.dumps({"error": "Not enough data"}))
    exit()

first_ts, first_sec = map(int, lines[0].split())
last_ts, last_sec = map(int, lines[-1].split())

history = []

for line in lines:
    ts, sectors = map(int, line.strip().split())
    gb = sectors * 512 / (1024**3)
    history.append({"time": ts, "gb": round(gb, 2)})

total_tb = last_sec * 512 / (1024**4)

# 今日写入
now = int(time.time())
today_start = now - 86400
today_lines = [l for l in lines if int(l.split()[0]) > today_start]

today_gb = 0
if len(today_lines) >= 2:
    s1 = int(today_lines[0].split()[1])
    s2 = int(today_lines[-1].split()[1])
    today_gb = (s2 - s1) * 512 / (1024**3)

# 平均每日
total_days = max((last_ts - first_ts) / 86400, 1)
avg_daily_gb = (last_sec - first_sec) * 512 / (1024**3) / total_days

life_used_percent = (total_tb / TBW_LIMIT_TB) * 100
remaining_tb = TBW_LIMIT_TB - total_tb
remaining_years = 0

if avg_daily_gb > 0:
    remaining_days = (remaining_tb * 1024) / avg_daily_gb
    remaining_years = remaining_days / 365

alert = today_gb > ALERT_GB_PER_DAY

# ========= 电池 =========
battery_percent = None
battery_status = None

for p in os.listdir("/sys/class/power_supply"):
    path = f"/sys/class/power_supply/{p}"
    if "battery" in p.lower():
        try:
            with open(path + "/capacity") as f:
                battery_percent = int(f.read().strip())
            with open(path + "/status") as f:
                battery_status = f.read().strip()
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
                if 1000 < temp < 120000:  # 过滤无效值
                    temperature_c = round(temp / 1000, 1)
                    break
except:
    pass

# ========= 无线 IP =========
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

result = {
    "history": history,
    "total_tb": round(total_tb, 2),
    "today_gb": round(today_gb, 2),
    "avg_daily_gb": round(avg_daily_gb, 2),
    "life_used_percent": round(life_used_percent, 2),
    "remaining_years": round(remaining_years, 2),
    "battery_percent": battery_percent,
    "battery_status": battery_status,
    "temperature_c": temperature_c,
    "wifi_ip": wifi_ip,
    "alert": alert
}

print("Content-Type: application/json\n")
print(json.dumps(result))
