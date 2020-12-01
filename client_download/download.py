import aiopubsub
import argparse
import asyncio
import os

import view
from downloader import Downloader, filter_videos, read_source_file


# * `-d`: Deletes files in the input with the result `delete`
# * `-D`: Deletes files in the input csv from the server that would otherwise be downloaded
# * `-k`: Downloads files with the results `keep`, `keep_audio`, etc.
# * `-a`: Downloads files with the results `archive_audio`, `archive_video+subs`, etc.
# * `-i`: Downloads files with the result `inspect`
# * `-m`: Downloads and merges files with the results `audio`, `audio+subs`, `video`, `video+subs`, `audio+video`, and `subs`
# * `-t`: Interpret the input files as tab-separated UTF-16 rather than comma-separated UTF-8.
#
# To download files and delete them from the server, run for example `download.py -k` followed by `download.py -Dk`.
#  `downtape.py` does this, with a `writetape` in the middle.
#
# The server is found from the `Server` column in the csv file. Pass `--server-map`, which should
# map server names to rclone server names (one-to-many):
# ```
# octopus,/bucket/archives/dl
# octopus,panray:projects/rtbak/dl/meta/metadata
# wasabi,wasabi-us:sdg-spout
# wasabi,wasabi-eu:eurospout
# wasabi,panray:projects/rtbak/dl/meta/metadata
# ```
# It checks for the video file and corresponding info.json and thumbnail on each server matching `Server`.
#
# If you've used `download_server_metadata`, make sure to include the new location of the metadata files as a possible server.
#
# The thumbnail and info.json are added as attachments to the mkv file after it is downloaded.
# (non-mkv video files are remuxed into an mkv file)
#
# If `other_server` and `other_path` are given in the csv, it will include thumbnails and info.json from those too.
#
# Thumbnail files are deleted by `-d` and `-D`, but info.json files are not.
#
# The mappings from original filenames to renamed filenames (many-to-one, in case of `-m`) in a log file specified by `-o`.
#
# (This way the metadata left behind can be matched to the stored video files later.)

async def download(args, hub):
	downloader = Downloader(hub=hub, prefix='dl', output_dir=args.output,
	                        output_file=args.map_output,
	                        server_map_file=args.server_map, dry_run=args.dry_run)
	all_videos = read_source_file(filename=args.source, tsv=args.tab_separated)
	args.server_map.close()

	job_options = {'download': not args.delete_instead, 'delete': args.delete_instead or args.move}

	tasks = []

	if args.delete:
		tasks.append(downloader.download(filter_videos(all_videos, 'delete'),
		                                 download=False, delete=True, keys=['delete']))
	if args.keep:
		tasks.append(downloader.download_and_merge(
			filter_videos(all_videos, 'keep'), **job_options, keys=['keep']))
	if args.archive:
		tasks.append(downloader.download(filter_videos(all_videos, 'archive'), **job_options,
		                                 keys=['inspect']))
	if args.inspect:
		tasks.append(downloader.download(filter_videos(all_videos, 'inspect'), **job_options,
		                                 keys=['inspect']))
	if args.merge:
		tasks.append(downloader.download_and_merge(
			filter_videos(all_videos, 'subs', 'audio', 'audio+video', 'video', 'video+subs',
			              'audio+subs'), **job_options, keys=['merge']))

	await asyncio.gather(*tasks)

	args.map_output.close()
	args.log_output.close()


def main():
	parser = argparse.ArgumentParser(
		description="Identify preferable versions of RoosterTeeth videos in a processed vidinfo csv file")
	parser.add_argument('source', help="vidinfo csv file")
	parser.add_argument('-d', '--delete', action='store_true',
	                    help='Delete files with the result "delete"')
	parser.add_argument('-D', '--delete-instead', action='store_true',
	                    help='Delete files that would otherwise be downloaded')
	parser.add_argument('-M', '--move', action='store_true', help='Delete files after downloading')
	parser.add_argument('-k', '--keep', action='store_true',
	                    help='Download, merge, and rename files with the results "keep", "keep_*"')
	parser.add_argument('-a', '--archive', action='store_true',
	                    help='Download files with the result "archive", "archive_*"')
	parser.add_argument('-i', '--inspect', action='store_true',
	                    help='Download files with the result "inspect"')
	parser.add_argument('-m', '--merge', action='store_true',
	                    help='Download, merge, and rename files with the results "audio", '
	                         '"video+subs", etc.')
	parser.add_argument('-t', '--tab-separated', action='store_true',
	                    help='Interpret input file as UTF-16 TSV rather than UTF-8 CSV')
	parser.add_argument('--map-output', nargs='?', type=argparse.FileType('a'), default=os.devnull,
	                    help="log file with mappings from original filenames to renamed filenames")
	parser.add_argument('--log-output', help="log file with all output (will be overwritten)",
	                    nargs='?', type=argparse.FileType('w'), default=os.devnull)
	parser.add_argument('-o', '--output')
	parser.add_argument('-n', '--dry-run', action='store_true',
	                    help="Perform a dry run")
	parser.add_argument('--server-map', help="Server map CSV file", type=argparse.FileType('r'))

	args = parser.parse_args()
	hub = aiopubsub.Hub()

	ui = view.DownloadView(logfile=args.log_output, hub=hub)
	try:
		asyncio.run(download(args, hub))
	finally:
		del ui


if __name__ == "__main__":
	main()
