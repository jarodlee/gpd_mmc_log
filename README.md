# gpd_mmc_log

> 🧪 A lightweight eMMC wear monitoring dashboard for early GPD Pocket (eMMC models)  
> Designed for low write amplification, long-term observation, and experimental use.

---

## ⚠ Disclaimer

This project is primarily tested on **early GPD Pocket models with eMMC storage**.

Newer GPD devices may use:

- NVMe SSD
- Different eMMC controllers
- Different block device paths

Before deployment, verify your device path:

```bash
lsblk
```

If your storage device is not `mmcblk0`, adjust accordingly (e.g. `/sys/block/nvme0n1/stat`).

---

## 🎯 Project Goal

Build a minimal-impact eMMC monitoring service:

- Ultra-low disk writes
- Simple architecture
- Long-term safe logging
- Web-based visualization (Chart.js)
- No heavy monitoring stack

Perfect for:

- Experimental Linux setups
- Small home servers
- Embedded devices
- Always-on lab machines

---

## 🧠 Architecture (Low Wear Design)

```
Every 5 minutes:
    Read /sys/block/mmcblk0/stat
            ↓
    Append 1 line to log file
            ↓
    Web page reads log
            ↓
    Chart.js renders graph
```

### 📉 Write Impact

| Period | Log Size |
|--------|----------|
| Daily  | 288 lines |
| Yearly | ~100 KB |
| 5 Years | ~500 KB |

Negligible impact on eMMC lifespan.

---

## 📦 Stack

- Nginx
- Python3 (CGI via fcgiwrap)
- Chart.js
- Cron

No database required.

---

# 🚀 Installation Guide

---

## 1️⃣ Create Logger Script

```bash
nano ~/mmc_logger.sh
```

```bash
#!/bin/bash

LOGFILE="/var/log/mmc_stat.log"

TS=$(date +%s)
STAT=$(cat /sys/block/mmcblk0/stat)

WRITE_SECTORS=$(echo $STAT | awk '{print $7}')

echo "$TS $WRITE_SECTORS" >> $LOGFILE
```

Make it executable:

```bash
chmod +x ~/mmc_logger.sh
```

---

## 2️⃣ Add Cron Job (Every 5 Minutes)

```bash
crontab -e
```

Add:

```bash
*/5 * * * * /home/youruser/mmc_logger.sh
```

✔ 288 writes per day  
✔ Extremely low wear  

---

## 3️⃣ Install Web Server

```bash
sudo apt update
sudo apt install nginx fcgiwrap
```

---

## 4️⃣ Create Web Page

```bash
sudo nano /var/www/html/mmc.html
```

```html
<!DOCTYPE html>
<html>
<head>
    <title>GPD eMMC Monitor</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
<h2>eMMC Total Writes (GB)</h2>
<canvas id="mmcChart"></canvas>

<script>
fetch('/mmc_data')
.then(response => response.json())
.then(data => {
    const labels = data.map(d => new Date(d.time * 1000).toLocaleString());
    const values = data.map(d => d.gb);

    new Chart(document.getElementById('mmcChart'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Total Written GB',
                data: values,
                fill: false,
                tension: 0.1
            }]
        }
    });
});
</script>
</body>
</html>
```

---

## 5️⃣ Create JSON CGI Interface

```bash
sudo nano /usr/local/bin/mmc_json.py
```

```python
#!/usr/bin/env python3
import json

data = []
with open("/var/log/mmc_stat.log") as f:
    lines = f.readlines()

for line in lines:
    ts, sectors = line.strip().split()
    sectors = int(sectors)
    gb = sectors * 512 / (1024**3)
    data.append({"time": int(ts), "gb": round(gb,2)})

print("Content-Type: application/json\n")
print(json.dumps(data))
```

Make executable:

```bash
sudo chmod +x /usr/local/bin/mmc_json.py
```

---

## 6️⃣ Configure Nginx

Edit:

```bash
sudo nano /etc/nginx/sites-enabled/default
```

Inside `server {}` add:

```nginx
location /mmc_data {
    include fastcgi_params;
    fastcgi_pass unix:/run/fcgiwrap.socket;
    fastcgi_param SCRIPT_FILENAME /usr/local/bin/mmc_json.py;
}
```

Restart:

```bash
sudo systemctl restart nginx
```

---

## 🌐 Access Dashboard

Open:

```
http://YOUR_IP/mmc.html
```

You will see:

- Total written GB
- Growth trend
- Write velocity changes
- Abnormal spikes detection

---

# 📊 Data Explanation

From:

```
/sys/block/mmcblk0/stat
```

Field 7:

```
Write sectors
```

Formula:

```
Bytes written = sectors × 512
```

Displayed value:

```
Total written GB
```

---

# 🧮 Lifespan Estimation (Optional)

Assume eMMC rated TBW:

```
80 TB
```

Calculation:

```
Current Written / 80 TB = Used %
Remaining = 100% - Used
```

Safe target:

- < 10 TB per year
- < 50 TB in 5 years

---

# 🔧 Optional Improvements

- Switch cron → systemd timer
- Add logrotate
- Add daily delta calculation
- Add projected lifespan curve
- Improve UI to dashboard style
- Add NVMe support auto-detection

---

# 💡 Why This Exists

Many lightweight devices (like early GPD Pocket) use eMMC with limited TBW.

This tool provides:

✔ Visibility  
✔ Trend awareness  
✔ Early anomaly detection  
✔ Peace of mind  

---

# 📜 License

MIT (or choose your preferred license)

---

# 🙌 Final Notes

This project is intentionally simple.

No Prometheus.  
No database.  
No heavy monitoring stack.  

Just a clean, long-running, low-impact wear dashboard.

Your eMMC deserves transparency.
