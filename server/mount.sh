#!/usr/bin/env bash
s3fs sdg-spout /mnt/bucket -o passwd_file=/etc/passwd-s3fs -o url=https://s3.us-west-1.wasabisys.com
s3fs eurospout /mnt/euro -o passwd_file=/etc/passwd-s3fs -o url=https://s3.eu-central-1.wasabisys.com
