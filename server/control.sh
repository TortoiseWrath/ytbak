#!/usr/bin/env bash

for (( ; ; )); do

    SECONDS=0
    ./merge.sh

    # Start downloading.
    echo "Starting ytdl1"
    ./download1.sh &
    echo "Starting ytdl2"
    ./download2.sh &
    echo "Starting ytdl3"
    ./download3.sh &
    echo "Starting ytdl4"
    ./download4.sh &

    FREE_SPACE=0
    YTDL_DEAD=0

    while (( YTDL_DEAD == 0 )); do
        FREE_SPACE=$(df . | awk 'NR==2{print $4}')
        echo "Free space is $FREE_SPACE."
        if (( FREE_SPACE < 5000000 )) || (( SECONDS > 12000 )); then
            # Kill the downloader.
            echo "Free space is $FREE_SPACE. Killing ytdl"
            killall youtube-dl ffmpeg python
            YTDL_DEAD=1
        fi
        if (( FREE_SPACE < 5000000 )) || (( SECONDS <= 12000 )); then
            # Upload whatever is new.
            ./sync.sh
        fi
        # Loop
        sleep 10
    done
done
