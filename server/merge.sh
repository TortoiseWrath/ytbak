#!/usr/bin/env bash

cat /mnt/bucket/backup_ovh/archive.txt /mnt/bucket/backup/archive.txt /mnt/bucket/backup_us/archive.txt /mnt/bucket/backup/archive3.txt /mnt/bucket/backup_us/archive3.txt /mnt/bucket/backup_ovh/archive3.txt archive.txt archive3.txt | sort | uniq > archive_temp.txt
cp archive_temp.txt archive.txt
cp archive_temp.txt archive3.txt
