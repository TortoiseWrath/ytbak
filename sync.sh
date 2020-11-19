#!/usr/bin/env bash

rclone move dl/ euro:eurospout --min-age 2m --filter "- *.temp.mkv" --filter "+ *.mkv" --filter "+ *.webp" --filter "+ *.json" --filter "+ *.jpg" --filter "+ *.info.json" --filter "+ *.png" --filter "+ *\].mp4" --filter "- *" -P
