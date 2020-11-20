#!/usr/bin/env bash

youtube-dl --download-archive archive2.txt \
    --write-info-json \
    --write-sub --write-auto-sub --all-subs --embed-subs \
    --ignore-errors \
    --write-annotations \
    --write-thumbnail \
    --output "dl/RT/%(series)s - %(episode_number)s - %(title)s [%(id)s].%(ext)s" \
    --merge-output-format "mkv" \
    --batch-file "download2.txt" \
    --prefer-ffmpeg &>> download2.log