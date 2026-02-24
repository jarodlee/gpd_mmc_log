#!/bin/bash

LOGFILE="/var/log/mmc_stat.log"

TS=$(date +%s)
STAT=$(cat /sys/block/mmcblk0/stat)

WRITE_SECTORS=$(echo $STAT | awk '{print $7}')

echo "$TS $WRITE_SECTORS" >> $LOGFILE
