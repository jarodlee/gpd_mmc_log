# gpd_mmc_log
使用chatgpt帮助我在gpd小电脑上搭一个简单的服务来监控mmc的使用情况

服务基于nginx和python3

相对应的文件位置

sudo nano /usr/local/bin/mmc_json.py

架构设计（低磨损）
每 5 分钟读取 /sys/block/mmcblk0/stat
        ↓
只记录 1 行数据到日志（极低写入）
        ↓
网页读取日志
        ↓
Chart.js 画图
每天写入日志不到 10KB，几乎可忽略。
第一步：创建数据采集脚本
nano ~/mmc_logger.sh
写入：
#!/bin/bash

LOGFILE="/var/log/mmc_stat.log"

TS=$(date +%s)
STAT=$(cat /sys/block/mmcblk0/stat)

WRITE_SECTORS=$(echo $STAT | awk '{print $7}')

echo "$TS $WRITE_SECTORS" >> $LOGFILE
赋权限：
chmod +x ~/mmc_logger.sh
第二步：定时任务（5分钟一次）
crontab -e
加入：
*/5 * * * * /home/jarod/mmc_logger.sh
✔ 每天只写 288 行
✔ 每年日志 ≈ 100KB
✔ 5 年 ≈ 500KB
对 eMMC 几乎无压力。
第三步：安装轻量 Web 服务
sudo apt install nginx
第四步：创建网页
sudo nano /var/www/html/mmc.html

第五步：创建数据接口（关键）
创建：
sudo nano /usr/local/bin/mmc_json.py
写入：
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
赋权限：
sudo chmod +x /usr/local/bin/mmc_json.py
第六步：配置 nginx CGI
安装：
sudo apt install fcgiwrap
编辑 nginx：
sudo nano /etc/nginx/sites-enabled/default
在 server 块里加入：
location /mmc_data {
    include fastcgi_params;
    fastcgi_pass unix:/run/fcgiwrap.socket;
    fastcgi_param SCRIPT_FILENAME /usr/local/bin/mmc_json.py;
}
重启：
sudo systemctl restart nginx

访问页面
浏览器打开：
http://你的IP/mmc.html
你会看到：
累计写入 GB 曲线
趋势变化
实时增长
写入量解释（你会看到什么）
/sys/block/mmcblk0/stat 第 7 列：
写入扇区数
计算：
写入字节 = 扇区数 × 512
页面显示的是：
累计写入 GB
你可以观察：
每天增长多少
每月增长多少
是否异常暴涨
进阶（我建议你加）
可以再加一行显示：
预计总 TBW 80TB
当前使用百分比
我可以帮你算出：
寿命剩余 %
对你这台实验机的意义
你目标 5 年：
只要：
年写入 < 10TB
5 年 < 50TB
基本稳。
这个页面就是你的“磨损仪表盘”。


