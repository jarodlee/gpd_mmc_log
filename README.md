# gpd_mmc_log

Lightweight GPD eMMC and system status dashboard for an nginx + fcgiwrap setup.

This repository mirrors the web files currently deployed on the GPD:

- `index.html`: the silver NetOps landing page.
- `mmc.html`: browser dashboard for eMMC/system status.
- `mmc_json.py`: Python CGI backend used by `/mmc_data`.

## Current Deployment

On the GPD:

```bash
/var/www/html/index.html
/var/www/html/mmc.html
/var/www/mmc/mmc_json.py
/usr/local/bin/mmc_json.py -> /var/www/mmc/mmc_json.py
```

The nginx endpoint `/mmc_data` is served through `fcgiwrap` and points to
`/usr/local/bin/mmc_json.py`, which is a symlink to the copy in `/var/www/mmc`.

## What It Monitors

- eMMC device name/model/size
- daily write amount from `/proc/diskstats`
- estimated TB written since the local baseline
- eMMC EXT_CSD health fields, refreshed by a root timer
- battery status
- temperature
- Wi-Fi IP
- CPU usage
- memory usage based on `MemAvailable`
- ZFS ARC size

The backend automatically detects the real non-removable `mmcblk*` disk. This
matters on the current GPD because the real disk is `mmcblk1`, not `mmcblk0`.

## Remaining Life Estimate

The dashboard deliberately avoids showing silly lifetime estimates.

It uses today's latest write amount as the estimate basis, but only shows a
specific remaining lifetime when both are true:

- normal sample days are at least 30
- the calculated estimate is not greater than 20 years

Otherwise it displays an explanatory message such as:

```text
采样正常天数 3/30，暂无可靠估算
```

The eMMC hardware health fields are usually more trustworthy than a long-term
projection:

- `Life Time Estimation A`
- `Pre EOL information`

## Runtime Files

Runtime state is intentionally not part of the dashboard source:

```bash
/var/www/mmc/mmc_state.json
/var/www/mmc/mmc_history.json
/var/www/mmc/extcsd.log
/var/www/mmc/mmc_state.lock
```

## Useful Commands

```bash
curl http://127.0.0.1/mmc_data | python3 -m json.tool
systemctl status fcgiwrap
systemctl status mmc-extcsd-refresh.timer
/usr/local/sbin/update_mmc_extcsd.sh
nginx -t
```

## Nginx Snippet

The GPD currently exposes `/mmc_data` with:

```nginx
location /mmc_data {
    include fastcgi_params;
    fastcgi_pass unix:/run/fcgiwrap.socket;
    fastcgi_param SCRIPT_FILENAME /usr/local/bin/mmc_json.py;
}
```
