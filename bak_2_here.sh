#!/bin/bash

FILES=(
"/usr/local/bin/mmc_json.py"
"/var/www/html/mmc.html"
"/var/www/mmc/mmc_state.json"
)

RED="\033[31m"
GREEN="\033[32m"
YELLOW="\033[33m"
NC="\033[0m"

get_info() {
    if [ -f "$1" ]; then
        size=$(stat -c %s "$1")
        mtime=$(stat -c %Y "$1")
        echo "${size}_${mtime}"
    else
        echo "0_0"
    fi
}

echo "====== Checking changes before overwrite ======"
echo

for f in "${FILES[@]}"; do
    src="$f"
    dst="./$(basename "$f")"

    before=$(get_info "$dst")

    sudo cp "$src" ./ 2>/dev/null

    after=$(get_info "$dst")

    if [ "$before" != "$after" ]; then
        size=$(stat -c %s "$dst")
        mtime=$(stat -c "%y" "$dst" | cut -d'.' -f1)

        echo -e "${RED}CHANGED:${NC} $(basename "$f")"
        echo -e "  ${YELLOW}Size:${NC} $size bytes"
        echo -e "  ${YELLOW}Modified:${NC} $mtime"
        echo
    fi
done

echo -e "${GREEN}Done.${NC}"
