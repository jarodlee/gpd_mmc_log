#!/usr/bin/env python3
import datetime
import fcntl
import json
import os
import re
import subprocess
import time
from pathlib import Path

TBW_LIMIT_TB = 80
ALERT_GB_PER_DAY = 30
BATTERY_ALERT_LEVEL = 20
MAX_RELIABLE_REMAINING_YEARS = 20
MIN_RELIABLE_SAMPLE_DAYS = 30
MIN_NORMAL_DAY_GB = 0.01

STATE_DIR = Path("/var/www/mmc")
STATE_FILE = STATE_DIR / "mmc_state.json"
HISTORY_FILE = STATE_DIR / "mmc_history.json"
EXTCSD_FILE = STATE_DIR / "extcsd.log"
LOCK_FILE = STATE_DIR / "mmc_state.lock"


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def atomic_write_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def run_text(cmd):
    return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()


def list_emmc_disks():
    disks = []
    for sys_path in Path("/sys/block").glob("mmcblk*"):
        name = sys_path.name
        if "boot" in name or "rpmb" in name or name[-1:].isdigit() is False:
            continue
        removable = (sys_path / "removable").read_text().strip() if (sys_path / "removable").exists() else "0"
        size_sectors = int((sys_path / "size").read_text().strip())
        if removable == "1" or size_sectors <= 0:
            continue
        model = ""
        if (sys_path / "device/name").exists():
            model = (sys_path / "device/name").read_text().strip()
        disks.append({
            "name": name,
            "path": f"/dev/{name}",
            "model": model,
            "size_sectors": size_sectors,
        })
    disks.sort(key=lambda x: x["size_sectors"], reverse=True)
    return disks


def get_diskstats_sector(disk_name):
    with open("/proc/diskstats") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 14 and parts[2] == disk_name:
                return int(parts[9])
    return None


def update_write_stats(disk):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    today = str(datetime.date.today())
    current_sector = get_diskstats_sector(disk["name"])
    if current_sector is None:
        current_sector = 0

    with open(LOCK_FILE, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = load_json(STATE_FILE, {
            "disk_name": disk["name"],
            "last_sector": current_sector,
            "total_sector": 0,
            "daily_sector": 0,
            "last_day": today,
            "first_ts": int(time.time()),
        })

        for key, value in {
            "total_sector": 0,
            "daily_sector": 0,
            "first_ts": int(time.time()),
            "last_day": today,
        }.items():
            state.setdefault(key, value)

        old_disk = state.get("disk_name")
        last_sector = int(state.get("last_sector") or 0)

        if old_disk != disk["name"]:
            # Do not turn an old/wrong disk baseline into a huge fake daily write.
            delta = 0
            state["disk_name"] = disk["name"]
            state["last_sector"] = current_sector
            state["daily_sector"] = 0
            state["last_day"] = today
        else:
            delta = current_sector - last_sector
            if delta < 0:
                # Kernel diskstats reset after reboot. Start a fresh baseline.
                delta = 0
            if state.get("last_day") != today:
                state["daily_sector"] = 0
                state["last_day"] = today
            state["total_sector"] = int(state.get("total_sector") or 0) + delta
            state["daily_sector"] = int(state.get("daily_sector") or 0) + delta
            state["last_sector"] = current_sector

        atomic_write_json(STATE_FILE, state)
        fcntl.flock(lock, fcntl.LOCK_UN)
        return state


def update_history(today_gb):
    today = str(datetime.date.today())
    history = load_json(HISTORY_FILE, [])
    by_date = {}
    for item in history:
        if isinstance(item, dict) and "date" in item:
            by_date[item["date"]] = {
                "date": item["date"],
                "gb": round(float(item.get("gb") or 0), 2),
            }
    by_date[today] = {"date": today, "gb": round(today_gb, 2)}
    history = [by_date[k] for k in sorted(by_date.keys())][-30:]
    atomic_write_json(HISTORY_FILE, history)
    return history


def read_emmc_health():
    text = ""
    try:
        text = EXTCSD_FILE.read_text(errors="ignore")
    except Exception:
        return None, None

    life_a = None
    pre_eol = None
    for line in text.splitlines():
        if "Life Time Estimation A" in line:
            match = re.search(r"0x([0-9A-Fa-f]+)", line)
            if match:
                life_a = int(match.group(1), 16)
        elif "Pre EOL information" in line:
            match = re.search(r"0x([0-9A-Fa-f]+)", line)
            if match:
                pre_eol = int(match.group(1), 16)
    return life_a, pre_eol


def read_battery():
    try:
        for p in os.listdir("/sys/class/power_supply"):
            path = Path("/sys/class/power_supply") / p
            if "battery" not in p.lower():
                continue
            percent = int((path / "capacity").read_text().strip())
            status = (path / "status").read_text().strip()
            return percent, status, percent < BATTERY_ALERT_LEVEL
    except Exception:
        pass
    return None, None, False


def read_temperature():
    temps = []
    try:
        for zone in Path("/sys/class/thermal").glob("thermal_zone*"):
            temp_path = zone / "temp"
            if not temp_path.exists():
                continue
            temp_raw = int(temp_path.read_text().strip())
            if 1000 < temp_raw < 120000:
                label = ""
                if (zone / "type").exists():
                    label = (zone / "type").read_text().strip()
                temps.append((label, round(temp_raw / 1000, 1)))
    except Exception:
        pass
    if not temps:
        return None
    for label, temp in temps:
        if any(key in label.lower() for key in ["cpu", "x86", "core", "soc"]):
            return temp
    return max(temp for _, temp in temps)


def read_wifi_ip():
    try:
        output = run_text(["ip", "-4", "-o", "addr", "show", "scope", "global"])
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 4 and re.match(r"wl|wlan", parts[1]):
                return parts[3].split("/")[0]
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                return parts[3].split("/")[0]
    except Exception:
        pass
    return None


def read_cpu_usage():
    def read_cpu():
        with open("/proc/stat") as f:
            parts = list(map(int, f.readline().strip().split()[1:]))
        idle = parts[3] + parts[4]
        total = sum(parts)
        return idle, total

    try:
        idle1, total1 = read_cpu()
        time.sleep(0.1)
        idle2, total2 = read_cpu()
        total_delta = total2 - total1
        if total_delta <= 0:
            return None
        idle_delta = idle2 - idle1
        return round(100 * (1 - idle_delta / total_delta), 1)
    except Exception:
        return None


def read_mem_used_percent():
    try:
        meminfo = {}
        with open("/proc/meminfo") as f:
            for line in f:
                key, value = line.split(":", 1)
                meminfo[key] = int(value.strip().split()[0])
        total = meminfo["MemTotal"]
        available = meminfo.get("MemAvailable")
        if not available or total <= 0:
            return None
        return round((1 - available / total) * 100, 1)
    except Exception:
        return None


def read_arc_size_gb():
    try:
        with open("/proc/spl/kstat/zfs/arcstats") as f:
            for line in f:
                if line.startswith("size"):
                    return round(int(line.split()[2]) / (1024**3), 2)
    except Exception:
        pass
    return None


def main():
    disk = (list_emmc_disks() or [{
        "name": None,
        "path": None,
        "model": None,
        "size_sectors": 0,
    }])[0]

    if disk["name"]:
        state = update_write_stats(disk)
    else:
        now = int(time.time())
        state = {
            "disk_name": None,
            "last_sector": 0,
            "total_sector": 0,
            "daily_sector": 0,
            "last_day": str(datetime.date.today()),
            "first_ts": now,
        }

    today_gb = state["daily_sector"] * 512 / (1024**3)
    total_tb = state["total_sector"] * 512 / (1024**4)
    history_data = update_history(today_gb)

    total_days = max((int(time.time()) - int(state.get("first_ts") or int(time.time()))) / 86400, 1)
    total_gb = state["total_sector"] * 512 / (1024**3)
    avg_daily_gb = total_gb / total_days
    life_used_percent = max(total_tb / TBW_LIMIT_TB * 100, 0)
    remaining_tb = max(TBW_LIMIT_TB - total_tb, 0)

    sample_days = len(history_data)
    normal_sample_days = sum(1 for item in history_data if float(item.get("gb") or 0) >= MIN_NORMAL_DAY_GB)
    latest_daily_gb = today_gb
    raw_remaining_years = None
    remaining_years = None
    remaining_estimate_reliable = False
    remaining_estimate_note = "今天写入量为 0，暂无可靠估算"

    if latest_daily_gb > 0:
        raw_remaining_years = (remaining_tb * 1024 / latest_daily_gb) / 365
        if normal_sample_days < MIN_RELIABLE_SAMPLE_DAYS:
            remaining_estimate_note = f"采样正常天数 {normal_sample_days}/{MIN_RELIABLE_SAMPLE_DAYS}，暂无可靠估算"
        elif raw_remaining_years > MAX_RELIABLE_REMAINING_YEARS:
            remaining_estimate_note = f"按今天写入量估算超过 {MAX_RELIABLE_REMAINING_YEARS} 年，写入量过低，暂无可靠估算"
        else:
            remaining_years = raw_remaining_years
            remaining_estimate_reliable = True
            remaining_estimate_note = "按今天最新写入量估算"

    emmc_life_a, emmc_pre_eol = read_emmc_health()
    battery_percent, battery_status, battery_alert = read_battery()

    result = {
        "history": history_data,
        "disk_name": disk["name"],
        "disk_model": disk["model"],
        "disk_size_gb": round(disk["size_sectors"] * 512 / (1024**3), 1) if disk["size_sectors"] else None,
        "total_tb": round(total_tb, 2),
        "today_gb": round(today_gb, 2),
        "avg_daily_gb": round(avg_daily_gb, 2),
        "life_used_percent": round(life_used_percent, 2),
        "remaining_years": round(remaining_years, 2) if remaining_years is not None else None,
        "raw_remaining_years": round(raw_remaining_years, 2) if raw_remaining_years is not None else None,
        "remaining_estimate_reliable": remaining_estimate_reliable,
        "remaining_estimate_note": remaining_estimate_note,
        "sample_days": sample_days,
        "normal_sample_days": normal_sample_days,
        "estimate_basis_gb_per_day": round(latest_daily_gb, 2),
        "emmc_life_level": emmc_life_a,
        "emmc_pre_eol": emmc_pre_eol,
        "battery_percent": battery_percent,
        "battery_status": battery_status,
        "battery_alert": battery_alert,
        "temperature_c": read_temperature(),
        "wifi_ip": read_wifi_ip(),
        "cpu_usage": read_cpu_usage(),
        "mem_used_percent": read_mem_used_percent(),
        "arc_size_gb": read_arc_size_gb(),
        "alert": today_gb > ALERT_GB_PER_DAY,
    }

    print("Content-Type: application/json")
    print()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
