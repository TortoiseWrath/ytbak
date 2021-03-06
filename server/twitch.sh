#!/usr/bin/env bash

youtube-dl --download-archive archive.txt \
  --write-info-json \
  --write-sub --write-auto-sub --all-subs --embed-subs \
  --ignore-errors \
  --write-annotations \
  --write-thumbnail \
  --output "dl/RT/%(series)s - %(episode_number)s - %(title)s [%(id)s].%(ext)s" \
  --merge-output-format "mkv" \
  --batch-file "channels.txt" \
  --prefer-ffmpeg &>>twitch.log
