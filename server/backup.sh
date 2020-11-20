#!/usr/bin/env bash
date >> /root/backup.log
cp /root/archive.txt "/mnt/bucket/archive/$(date +"%Y%m%d%H%M")_euro_archive1.txt"
cp /root/archive3.txt "/mnt/bucket/archive/$(date +"%Y%m%d%H%M")_euro_archive2.txt"
rsync -vaiWP --exclude "dl" --exclude "s3fs-fuse" ./ /mnt/bucket/backup/ | tee -a backup.log
