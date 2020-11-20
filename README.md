# ytbak

This is a collection of scripts I use to archive online videos.

`download1.sh` is the best one. The rest are mainly useful for specific use cases - namely, running different jobs in
parallel on distributed servers in the event deletion is threatened, manually organizing videos into folders and 
entering video metadata, and picking between or merging equivalent videos from RoosterTeeth.com and their YouTube channels.

## Server scripts
These scripts (*.sh) are run on remote servers that do the downloading. They upload files to s3 buckets, which are later
downloaded on a local server by client scripts. 

You could also run these locally. To avoid using s3 buckets, remove the call to `sync.sh` from `control.sh`, or simply 
run `download1.sh` directly. Also modify the rest of `control.sh` to your liking if using it.

They work on Debian. To get them working on FreeBSD I had to replace `killall` with `pkill -f` in `control.sh`.
They should work on everything else too with appropriate changes.

To run these:
* install dependencies: `bash`, [`youtube-dl`](https://github.com/ytdl-org/youtube-dl), `ffmpeg`, `rclone`, 
[`s3fs-fuse`](https://github.com/s3fs-fuse/s3fs-fuse)
* set up rclone, `sync.sh`, `merge.sh`, and `mount.sh` with appropriate buckets
* set up a cron job to run `backup.sh` periodically
* modify the scripts to fit what you're trying to do
* run `mount.sh`
* create files called `download1.txt` through `download4.txt`
with the contents suggested by the descriptions for `download1.sh` through `download4.sh`
* run `nohup ./run.sh &`
* monitor `download1.log` through `download4.log` and `run.log`

The `dl` directory will hold downloaded files until they are uploaded to the bucket.

You don't need s3fs and mount.sh: backup.sh/merge.sh could use rclone too, but I wrote it first before I figured out s3fs sucked and have no 
need to fix it. Fix it yourself if you want

### run.sh

This is just `./control.sh | tee -a run.log`.

### control.sh

This is the main controller, run by `run.sh`. 

It starts up `download1` through `download4`. 

It then runs `sync.sh` up to every 10 seconds to upload the downloaded files to the bucket.
If the free space drops below 5 GB, it kills the downloaders and waits for this to finish.

It also runs `merge.sh` and restarts the downloaders every 3 hours and 20 minutes while enough free space
is available to avoid them being restarted by the above.

### download1.sh through download4.sh

These are run by `control.sh` and run `youtube-dl`. 

Each one uses a corresponding archive file, `archive.txt` through `archive4.txt`. These get merged by `merge.sh`.

The downloads are taken from batch files in `download1.txt` through `download4.txt`. Make sure there's not too much
overlap between these, both across files and across servers. 
For example, you could put some playlists/videos/channels in `download2.txt` and others in 
`download4.txt`, where not many videos are in playlists in both files.
Or when using multiple servers, put one channel in `download1.txt` one one server and another channel in `download1.txt` 
on the other server.
Otherwise files can get downloaded twice. 
(This is mitigated slightly by the use of `merge.sh`.)

These output logs to `download1.log` through `download4.log`.

If one of the batch files is empty, the corresponding downloader will not run.

**`download1` and `download3` should not run simultaneously on the same server** due to YouTube's 529 lockout of naughty IPs.

These have different behavior:

* `download1.sh` is for downloading YouTube playlists and uses the output format `dl/%(playlist_uploader)s/%(playlist)s/%(playlist_index)s - %(uploader)s - %(upload_date)s - %(title)s [%(id)s].%(ext)s`
* `download2.sh` is for downloading videos with series from other sites and uses the output format `dl/RT/%(series)s - %(episode_number)s - %(title)s [%(id)s].%(ext)s`
* `download3.sh` is for downloading YouTube channels and uses the output format `dl/%(uploader)s/%(upload_date)s - %(title)s [%(id)s].%(ext)s`
* `download4.sh` is the same as `download2.sh`

The RT in the output format on download2.sh and download4.sh is because I was using it to download videos from RoosterTeeth.com.

Those two can run in parallel with no issue as long as there's no rate limiting on the video host.

### sync.sh

This uploads downloaded videos to the s3 bucket using rclone. Videos currently being downloaded are excluded, except when they aren't.

### merge.sh

This downloads archive files from each server's backups and merges them, so instances of youtube-dl started after this
will not download files that were already downloaded by another instance.

Currently it's only set up to do it for archive and archive3, as I was manually splitting individual videos into the
download2.txt and download4.txt files on each server.

### mount.sh

This mounts the mount points used by backup.sh and merge.sh using s3fs.

### backup.sh

This backs up the log files (and other stuff in the pwd, except the dl folder) to a bucket. 

`merge.sh` fetches the backed up archive files from other servers and uses them to guide downloads on current servers.

Nothing runs this; I set
up a cron job to do so on the VPS where this is running. 

## Client scripts

Once videos are downloaded, I run these locally to figure out what to do with them.

Dependencies for some of these: `bash`, python 3.9+, `jq`, `rclone`, `rsync`, `git`, `ffmpeg`, 
[`youtube-dl`](https://github.com/ytdl-org/youtube-dl), 
[MKVToolNix](https://mkvtoolnix.download/downloads.html),
[`writetape`](https://github.com/TortoiseWrath/shelf-of-interesting-items/blob/master/writetape)

`rclone` and `rsync` are used by `download_server_metadata` which should be modified appropriately

Workflow for RoosterTeeth videos:
* Extract the dates for RoosterTeeth.com videos from the HTML using `rtdates.py`
  * This is actually meant to parse the HTML I got from copying the entire video listing page into MS Word and saving it. Don't ask
* Download `info.json` files from the servers using `download_server_metadata`. (This deletes them from the servers, so keep track of them)
* See which videos are still alive
* Parse the `info.json` files using `vidinfo.py`, which creates a csv file
* Open the csv file in Excel, add and populate these columns, and save as another csv file:
  * Group,Series,Episode,Output Title,Part,Flag
* Further process _that_ file using `categorize.py`, to decide which sources of the same video to keep and which to delete
* Finish processing the resulting csv file manually in Excel
* TODO: Delete unwanted files from bucket using `download.py`
* TODO: Download flagged files from bucket using `download.py` and process them manually
* TODO: Download, merge as applicable, and rename files using `download.py` 
* Move files to where I want them; write certain videos to tape using `downtape.py`
* Delete 
* Periodically recheck alive videos using `check_alive`. Commit results; removed lines since last commit correspond to deleted videos

In Excel 2010, utf-8 encoded csv files have to be imported using "From Text" on the data tab. This creates a 
data connection; you can copy the imported data to another worksheet then import new data from an updated vidinfo.csv 
file by refreshing the connection. Then, save the updated worksheet as "Unicode Text (*.txt)" for processing by
categorize.py, download.py, and downtape.py and pass `-t` to these scripts to handle tab-separated files.

### download_server_metadata

This downloads `info.json` files from the servers configured in the script, removing them from the servers.

It places them in a `dl` folder, which needs to be a git repository, since it commits its results so I can keep track of them.

Don't run this twice in a row without running `vidinfo.py` in between; the first thing it does is move the contents of `dl/` to 
`dl/meta/`, which excludes them from the next run of vidinfo.py (when run as I do)

### vidinfo.py

This takes the downloaded `info.json` files and puts a bunch of useful information in a csv file. I run it as:

    python3.9 vidinfo.py -vrx meta -x streams --channel-map dl/meta/channelmap.csv --size-map dl/meta/ls-eu --size-map dl/meta/ls-us --date-map dl/meta/rtdates.csv --base-map dl/meta/basemap.csv --size-map dl/meta/ls-octopus -o dl/meta/vidinfo.csv dl

The way I have it set up, `ls-eu` should be the output of `rclone ls wasabi-eu:eurospout`, etc. 

It takes some arguments, some of which point to files that should be created manually first:

* `-x`, `--exclude`: exclude certain subdirectories of the target directory (in my case, meta and streams)
* `--size-map`: the output of `rclone ls wasabi-us:sdg-spout`, etc., so it knows how big the files are
* `--base-map`: this maps filename prefixes to the servers where I can find the file, which get removed from the "path" in the output csv. Mapping looks like:
```
/bucket/archives/dl,octopus
dl,wasabi
/root/dl,wasabi
```
* `--date-map`: a mapping from video id to upload date, in case it's not given in the json. I use this for RoosterTeeth videos using `rtdates.py`
* `--channel-map`: a mapping from video id to channel, in case it's not given in the json. For RoosterTeeth videos, I use this to map them to the "channel" equivalent they came from:
```
off-topic-2020-245,Achievement Hunter
top-10-wii-games,Rooster Teeth
```
* `-o`: output file

### rtdates.py

This parses the HTML file that I get from copying a fully-loaded video listing from RoosterTeeth.com and pasting it into MS Word and saving it as HTML
to determine the upload date corresponding to each video id.

This creates a `date-map` that can be used by `vidinfo.py`.

### categorize.py

Where both YT and RT sources exist for a video in a `vidinfo.csv` file (the output of `vidinfo.py`, plus additional columns as noted above),
this decides what to do with each one.

The option `-t` means it treats the input files as tab-separated UTF-16 rather than comma-separated UTF-8.

### download.py

Doesn't exist yet.

This one only needs Python 3.7, not Python 3.9.

This uses the decisions made by `categorize.py`, once I've manually inspected them, to do the following depending on which arguments are given:

* `-d`: Deletes files in the input with the result `delete`
* `-D`: Deletes files in the input csv from the server that would otherwise be downloaded
* `-k`: Downloads files with the results `keep`, `keep_audio`, etc.
* `-a`: Downloads files with the results `archive_audio`, `archive_video+subs`, etc.
* `-i`: Downloads files with the result `inspect`
* `-m`: Downloads and merges files with the results `audio`, `audio+subs`, `video`, `video+subs`, `audio+video`, and `subs`
* `-t`: Interpret the input files as tab-separated UTF-16 rather than comma-separated UTF-8.

To download files and delete them from the server, run for example `download.py -k` followed by `download.py -Dk`.
 `downtape.py` does this, with a `writetape` in the middle.

The server is found from the `Server` column in the csv file. Pass `--server-map` to `categorize.py`, which should 
map server names to rclone server names (one-to-many):
```
octopus,/bucket/archives/dl
octopus,panray:projects/rtbak/dl/meta/metadata
wasabi,wasabi-us:sdg-spout
wasabi,wasabi-eu:eurospout
wasabi,panray:projects/rtbak/dl/meta/metadata
```
It checks for the video file and corresponding info.json and thumbnail on each server matching `Server`.

If you've used `download_server_metadata`, make sure to include the new location of the metadata files as a possible server.

The thumbnail and info.json are added as attachments to the mkv file after it is downloaded. 
(non-mkv video files are remuxed into an mkv file)

If `other_server` and `other_path` are given in the csv, it will include thumbnails and info.json from those too. 

Thumbnail files are deleted by `-d` and `-D`, but info.json files are not.

The output filename is decided by the additional metadata fields in the csv. It can be in any of these formats:

* `{Group}/{Series}/{Date}`
* `{Group}/{Series}/{Date} - {Output Title}`
* `{Group}/{Series}/{Date} - Episode {Episode}`
* `{Group}/{Series}/{Date} - Episode {Episode} - {Output Title}`
* `{Group}/{Series}/{Date} - Part {Part}`
* `{Group}/{Series}/{Date} - {Output Title} - Part {Part}`
* `{Group}/{Series}/{Date} - Episode {Episode} - Part {Part}`
* `{Group}/{Series}/{Date} - Episode {Episode} - {Output Title} - Part {Part}`
* `{Group}/{Series}/{Output Title}` (if Output Title starts with S##E##)
* `{Group}/{Series}/{Output Title} - Part {Part}` (if Output Title starts with S##E##)
* `{Group}/{Date}`
* `{Group}/{Date} - {Output Title}`
* `{Group}/{Date} - Episode {Episode}`
* `{Group}/{Date} - Episode {Episode} - {Output Title}`
* `{Group}/{Date} - Part {Part}`
* `{Group}/{Date} - {Output Title} - Part {Part}`
* `{Group}/{Date} - Episode {Episode} - Part {Part}`
* `{Group}/{Date} - Episode {Episode} - {Output Title} - Part {Part}`

The mappings from original filenames to renamed filenames (many-to-one, in case of `-m`) in a log file specified by `-o`.

(This way the metadata and thumbnail images which are left behind can be matched to the stored video files later.)

### downtape.py

Doesn't exist yet.

This one only needs Python 3.7, not Python 3.9.

Note when writing this: https://unix.stackexchange.com/questions/346853/tar-list-files-break-on-first-file

Once I have results from `categorize.py`, I manually split the ones I _don't_ want to keep on my server into volumes with
the size of archival tapes, and use this to semi-automate the archival process.

Takes as an argument directory full of input CSV files, which are handled in order by filename.

Runs `download.py -k` on each one to download the files with the result `keep` into the directory 1/,
then runs `writetape` to write the downloaded files to tape and delete the local files.

While that tape is being written, it runs `download.py -k` on the next input file and saves them to 2/, etc.

Can put files in 1/, 2/, etc. before running this, to include things like the results of `download.py -m`. 

After writing a tape, it ejects the tape, deletes the files from the server with `download.py -Dk`, and waits until the next tape is inserted to start writing another one.

Before writing a tape, it makes sure the tape is blank. If the tape is not blank, it prompts and waits.

If free disk space drops below 1 TB, it stops downloading until enough tapes have been written that the free space is at least 1.5 TB. (this makes sense because I'm using LTO-3 tapes at the moment)

The option `-t` means it treats the input files as tab-separated UTF-16 rather than comma-separated UTF-8.

If `--copy-dead-to` is specified, files with alive=False (or a non-None falsy value) in the input file are copied to the specified destination 
before writing to tape. The destination specified is passed to rclone so should be in rclone format.

Note: Budget 250 KB extra per video on the tape, for thumbnails + info.json + overhead

## Credits & license

`download1.sh` and `download3.sh` incorporate the format specifier from 
[TheFrenchGhosty's YouTube-DL Archivist Scripts](https://github.com/TheFrenchGhosty/TheFrenchGhostys-YouTube-DL-Archivist-Scripts)
(licensed under GPL-3.0).

As such, this is also licensed under GPL-3.0.