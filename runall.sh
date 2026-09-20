#!/bin/bash
cd "$(dirname "$0")"
for c in deepsea_iceberg space_iceberg dead_star glass_rain greenland_shark anglerfish; do
  echo "=== $c $(date +%T)"
  python3 make_short.py "cfg/$c.json" 2>&1 | tail -3
done
echo "ALL DONE $(date +%T)"
