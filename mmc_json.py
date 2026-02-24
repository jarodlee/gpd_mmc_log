#!/usr/bin/env python3
import json
import time

TBW_LIMIT_TB = 80  # 128GB eMMC 保守估算
DAYS_PER_YEAR = 365

data = []
with open("/var/log/mmc_stat.log") as f:
    lines = f.readlines()

if len(lines) < 2:
    print("Content-Type: application/json\n")
    print(json.dumps({"error": "Not enough data"}))
    exit()

first_ts, first_sec = map(int, lines[0].split())
last_ts, last_sec = map(int, lines[-1].split())

# 历史曲线
for line in lines:
    ts, sectors = map(int, line.strip().split())
    gb = sectors * 512 / (1024**3)
    data.append({"time": ts, "gb": round(gb, 2)})

# 总写入 TB
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

# 平均每日写入
total_days = max((last_ts - first_ts) / 86400, 1)
avg_daily_gb = (last_sec - first_sec) * 512 / (1024**3) / total_days

# 预计剩余寿命
life_used_percent = (total_tb / TBW_LIMIT_TB) * 100

remaining_tb = TBW_LIMIT_TB - total_tb
remaining_days = 0
remaining_years = 0

if avg_daily_gb > 0:
    remaining_days = (remaining_tb * 1024) / avg_daily_gb
    remaining_years = remaining_days / DAYS_PER_YEAR

output = {
    "history": data,
    "total_tb": round(total_tb, 2),
    "today_gb": round(today_gb, 2),
    "avg_daily_gb": round(avg_daily_gb, 2),
    "life_used_percent": round(life_used_percent, 2),
    "remaining_years": round(remaining_years, 2)
}

print("Content-Type: application/json\n")
print(json.dumps(output))
