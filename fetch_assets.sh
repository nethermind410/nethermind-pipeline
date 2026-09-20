#!/bin/bash
# fetch_assets.sh — download every public-domain asset the current configs need.
# Safe to re-run: skips files that already exist. All sources are NASA/NOAA/ESA
# (public domain) or SIL Open Font License. Nothing here is copyrighted stock.
cd "$(dirname "$0")/assets" || exit 1
get () { # get <filename> <url>
  if [ -s "$1" ]; then echo "  have  $1"; return; fi
  printf "  get   %-26s " "$1"
  code=$(curl -s -L --max-time 180 -w "%{http_code}" -o "$1" "$2")
  size=$(wc -c < "$1" 2>/dev/null || echo 0)
  if [ "$code" = "200" ] && [ "$size" -gt 20000 ]; then echo "ok ${size}B"; else echo "FAILED (http $code, ${size}B)"; rm -f "$1"; fi
}

echo "Fonts (SIL Open Font License)"
get Anton-Regular.ttf     "https://raw.githubusercontent.com/google/fonts/main/ofl/anton/Anton-Regular.ttf"
get BebasNeue-Regular.ttf "https://raw.githubusercontent.com/google/fonts/main/ofl/bebasneue/BebasNeue-Regular.ttf"

echo "Space — NASA / Chandra X-ray Observatory (public domain)"
get casa_lg.jpg      "https://chandra.si.edu/photo/2024/casa/casa_lg.jpg"
get casa_life.jpg    "https://chandra.si.edu/photo/2020/sonify/sonify_casa_life.jpg"
get casa_sonify.mp4  "https://chandra.si.edu/photo/2020/sonify/sonify_casa_all_at_once.mp4"

echo "Exoplanet — ESA/Hubble (public domain)"
get hd189_art.jpg    "https://cdn.esahubble.org/archives/images/large/heic1312a.jpg"

echo "Ocean — NOAA (public domain)"
get shark_noaa.jpg      "https://www.fisheries.noaa.gov/s3//2023-06/979x550-Greenland-Shark-NOAA-OOER.jpg"
get shark_okeanos.jpg   "https://upload.wikimedia.org/wikipedia/commons/7/77/Somniosus_microcephalus_okeanos.jpg"
get angler1.jpg         "https://oceanexplorer.noaa.gov/wp-content/uploads/2025/04/anglerfish-hires.jpg"
get angler2.jpg         "https://oceanexplorer.noaa.gov/wp-content/uploads/2022/08/ex2206-dive06-anglerfish-hires.jpg"
get tubeworms.jpg       "https://oceanexplorer.noaa.gov/wp-content/uploads/2025/11/at-50-41-casm-tubeworms.jpg"

echo "Ocean depth zones — NOAA Ocean Exploration + NOAA Sanctuaries (public domain federal works)"
get reef_sunlight.jpg   "https://sanctuaries.noaa.gov/media/img/20121020-marine-life-coral-reefs-fagatele-wendy-cover-noaa-1000.jpg"
get barreleye.jpg       "https://oceanexplorer.noaa.gov/wp-content/uploads/2024/08/barreleye-fish.jpg"
get siphonophore.jpg    "https://oceanexplorer.noaa.gov/wp-content/uploads/2023/07/dive01-siphonophore-hires.jpg"

echo
echo "Done. Contents of assets/:"
ls -1sh . | grep -v '^total'
