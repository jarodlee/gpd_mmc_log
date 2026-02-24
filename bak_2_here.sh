#!/bin/bash

# ==========================================
# bak_2_here.sh
# 从系统目录拉取文件到当前目录（交互确认版）
# 默认安全策略：回车 = 退出
# ==========================================

FILES=(
"/usr/local/bin/mmc_json.py"
"/var/www/html/mmc.html"
"/var/www/mmc/mmc_state.json"
)

BACKUP_DIR="./.bak_$(date +%Y%m%d_%H%M%S)"
AUTO_YES=false

RED="\033[31m"
GREEN="\033[32m"
BLUE="\033[34m"
YELLOW="\033[33m"
NC="\033[0m"

echo
echo -e "${BLUE}====== Backup To Here (Safe Mode) ======${NC}"
echo -e "Direction: ${YELLOW}SYSTEM → CURRENT DIR${NC}"
echo

for src in "${FILES[@]}"; do
    name=$(basename "$src")
    dst="./$name"

    echo -e "${YELLOW}Checking:${NC} $name"

    if [ ! -f "$src" ]; then
        echo -e "${RED}Source not found:${NC} $src"
        echo
        continue
    fi

    # 本地不存在 → 新文件
    if [ ! -f "$dst" ]; then
        echo -e "${GREEN}[NEW FILE]${NC} $name"

        if [ "$AUTO_YES" = false ]; then
            read -p "Copy? (y = yes / a = all / q = quit) : " ans
        else
            ans="y"
        fi

        case "$ans" in
            y|Y)
                sudo cp "$src" "$dst"
                echo -e "${GREEN}Copied.${NC}"
                ;;
            a|A)
                AUTO_YES=true
                sudo cp "$src" "$dst"
                echo -e "${GREEN}Copied (AUTO MODE).${NC}"
                ;;
            *)
                echo "Quit."
                exit 0
                ;;
        esac

        echo
        continue
    fi

    # 已存在 → 对比
    if diff -u "$dst" "$src" > /dev/null; then
        echo -e "${GREEN}No differences.${NC}"
        echo
        continue
    fi

    echo -e "${RED}[DIFFERENCES DETECTED]${NC}"
    echo
    diff -u --color=always "$dst" "$src"
    echo

    if [ "$AUTO_YES" = false ]; then
        read -p "Overwrite local file? (y = yes / a = all / q = quit) : " ans
    else
        ans="y"
    fi

    case "$ans" in
        y|Y)
            ;;
        a|A)
            AUTO_YES=true
            ;;
        *)
            echo "Quit."
            exit 0
            ;;
    esac

    # 自动备份
    mkdir -p "$BACKUP_DIR"
    cp "$dst" "$BACKUP_DIR/$name.bak"

    sudo cp "$src" "$dst"

    echo -e "${GREEN}Updated.${NC}"
    echo -e "Backup saved to ${YELLOW}$BACKUP_DIR/$name.bak${NC}"
    echo

done

echo -e "${BLUE}====== Done ======${NC}"
echo
