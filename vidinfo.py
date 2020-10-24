import argparse
import csv
import json
import os
import re
import sys


class VideoMetadata:

	def __init__(self, info, date_map=None, base_map=None, size_map=None, channel_map=None):
		"""
		Construct a VideoMetadata object from an info.json file
		:param info: a dict resulting from decoding the info.json file
		:param date_map: a dict like {"video_id": "YYYY-MM-DD"}
		:param base_map: a list like [("/bucket", "Server 1")]
		:param size_map: a dict like {"video1.mkv": 40186938}
		:param channel_map: a dict like {"video_id": "An Excellent Channel"}
		"""
		if date_map is None:
			date_map = {}
		if base_map is None:
			base_map = []
		if size_map is None:
			size_map = {}
		if channel_map is None:
			channel_map = {}

		(self.server, self.filename) = VideoMetadata.split_path(info.get('_filename', ''), base_map)
		self.size = size_map.get(self.filename, None)
		self.website = info.get('extractor', None)
		self.id = info.get('display_id', None)
		self.channel = channel_map.get(self.id, None) or info.get('uploader', None)
		self.title = info.get('fulltitle', None) or info.get('title', None)
		self.date = date_map.get(self.id, None) or info['upload_date']

		# "Playlists": use series if present
		self.playlist_channel = info.get('playlist_uploader', '')
		self.playlist_index = info.get('episode_number', '') or info.get('playlist_index', '')
		if info.get('series', False):
			if info.get('season_number', False):
				self.playlist = f"{info['series']} Season {info['season_number']}"
			else:
				self.playlist = info['series']
		else:
			self.playlist = info.get('playlist', None)

		self.duration = info.get('duration', None)
		self.subtitles = len(info.get('subtitles', {}))

		downloaded_format = info.get('format_id', None)
		if '+' in downloaded_format:
			downloaded_format = downloaded_format.split('+')
			audio_format = downloaded_format[1]
			video_format = downloaded_format[0]
		else:
			audio_format = downloaded_format
			video_format = downloaded_format

		if audio_format is not None:
			audio_format = [x for x in info.get('formats', []) if x['format_id'] == audio_format][0]
		if video_format is not None:
			video_format = [x for x in info.get('formats', []) if x['format_id'] == video_format][0]

		try:
			self.abr = info.get('abr', None) or audio_format.get('abr', None)
			self.vbr = info.get('vbr', None) or video_format.get('vbr', None)
			self.bitrate = info.get('tbr', None) or video_format.get('tbr', None)
			self.acodec = info.get('acodec', None) or audio_format.get('acodec', None)
			self.vcodec = info.get('vcodec', None) or video_format.get('vcodec', None)
			self.height = info.get('height', None) or video_format.get('height', None)
			self.fps = info.get('fps', None) or video_format.get('fps', None)
		except TypeError:
			pass

		# Constant to convert bytes per second to kilobits per second
		kbps = 8 / 1024

		if self.abr and self.vbr and not self.bitrate:
			self.bitrate = self.abr + self.vbr
		if self.size and self.duration and not self.bitrate:
			self.bitrate = self.size / self.duration * kbps
		if self.bitrate and self.abr and not self.vbr:
			self.vbr = self.bitrate - self.abr
		if self.bitrate and self.vbr and not self.abr:
			self.abr = self.bitrate - self.vbr
		if self.abr and self.vbr and not self.bitrate:
			self.bitrate = self.abr + self.vbr

	csv_header = ["Server", "Filename", "Size", "Website", "ID", "Channel", "Playlist",
	              "Playlist channel",
	              "Playlist index", "Title", "Date", "Duration", "Subtitles",
	              "Video codec", "Height", "Video bitrate", "FPS", "Audio codec", "Audio bitrate",
	              "Total bitrate"]

	def __iter__(self):
		"""
		Iterate over instance variables in the order implied by self.csv_header
		:return: A list that can be written to csv to go with the csv header
		"""
		yield from (self.server, self.filename, self.size, self.website, self.id, self.channel,
		            self.playlist, self.playlist_channel, self.playlist_index, self.title,
		            self.date, self.duration, self.subtitles, self.vcodec, self.height, self.vbr,
		            self.fps, self.acodec, self.abr, self.bitrate)

	@staticmethod
	def split_path(filename, base_map):
		for basename, alias in base_map + [('/', '/')]:
			if filename.startswith(basename):
				return alias, filename.removeprefix(basename).removeprefix('/')
		print(f"Didn't find a basename (not even /) in filename {filename}", file=sys.stderr)
		return '', filename


def read_csv_maps(map_files):
	"""
	Read all map files and create a map
	:param map_files: list of filenames
	:return: a dict like {"video_id": "An Excellent Channel"}
	"""
	results = {}
	for filename in map_files or []:
		with open(filename, 'r') as file:
			reader = csv.reader(file)
			for row in reader:
				if len(row) == 0:
					continue
				if len(row) != 2:
					if len(row) != 0:
						print(f"Warning! The following row has length {len(row)} (should be 2)"
						      f" and is ignored:\n{row}\n",
						      file=sys.stderr)
					continue
				results[row[0]] = row[1]
	return results


size_map_pattern = re.compile(r'^\s*(\d+)\s+(.+)$')


def read_size_maps(size_maps):
	"""
	Read all size map files and create a size map
	:param size_maps: list of filenames
	:return: a dict like {"video1.mkv": 40186938}
	"""
	results = {}
	for filename in size_maps or []:
		with open(filename, 'r') as file:
			for line in file:
				match = size_map_pattern.match(line)
				if not match:
					print(f"Warning! The following sizemap row is invalid and ignored:\n{line}\n",
					      sys.stderr)
				else:
					results[match.group(2)] = int(match.group(1))
	return results


def read_base_maps(base_maps):
	"""
	Read all base map files and create a base map
	:param base_maps: list of filenames
	:return: a list like [("/bucket", "Server 1")]
	"""
	results = []
	for filename in base_maps or []:
		with open(filename, 'r') as file:
			reader = csv.reader(file)
			for row in reader:
				if len(row) == 0:
					continue
				if len(row) != 2:
					raise ValueError(f"Read basemap row {row} has length {len(row)} (should be 2)")
				results.append((row[0], row[1]))
	return results


def read_files(directory, logfile, excludes=None, date_map=None, base_map=None, channel_map=None,
               size_map=None, dry_run=False):
	if excludes is None:
		excludes = []
	videos = []

	files = 0

	for dirpath, dirnames, filenames in os.walk(directory):
		dirnames[:] = [dirname for dirname in dirnames if dirname not in excludes]
		for json_file in [os.path.join(dirpath, file) for file in filenames if
		                  file.endswith('.info.json')]:
			files += 1
			print(json_file, file=logfile)
			if not dry_run:
				with open(json_file) as f:
					data = json.load(f)
					videos.append(VideoMetadata(data, date_map=date_map, base_map=base_map,
					                            channel_map=channel_map, size_map=size_map))

	print(f"Found {files} json files", file=logfile)

	return videos


if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description="Finds info.json files in a directory and create a csv file with video metadata")
	parser.add_argument('source', help="info.json file or directory")
	parser.add_argument('-r', '--recursive', help="recurse into input directory",
	                    action='store_true')
	parser.add_argument('-x', '--exclude', help="files or directories to exclude from input",
	                    action='append')
	parser.add_argument('-o', '--output', help="output file", nargs='?',
	                    type=argparse.FileType('w'), default=sys.stdout)
	parser.add_argument('-v', '--verbose', help="print all filenames", action='store_true')
	parser.add_argument('-m', '--print-maps', help="print parsed maps", action='store_true')
	parser.add_argument('-n', '--dry-run', help="list info.json files only (implies -vm)",
	                    action='store_true')
	parser.add_argument('--date-map', help="csv file mapping video id to date", action='append')
	parser.add_argument('--channel-map', help="csv file mapping video id to channel",
	                    action='append')
	parser.add_argument('--size-map', help="list of filesizes (in format of 'rclone ls')",
	                    action='append')
	parser.add_argument('--base-map', help="csv file mapping base directories to servers",
	                    action='append')
	# TODO: Allow appending to the output file
	# TODO: Allow getting info from the video file
	args = parser.parse_args()

	dates = read_csv_maps(args.date_map)
	channels = read_csv_maps(args.channel_map)
	sizes = read_size_maps(args.size_map)
	bases = read_base_maps(args.base_map)

	if args.dry_run or args.verbose:
		if args.output == sys.stdout:
			verbose_output = sys.stderr
		else:
			verbose_output = sys.stdout
	else:
		verbose_output = open(os.devnull, 'w')

	if args.print_maps or args.dry_run:
		print(f"Date map with {len(dates)} entries:\n{dates}\n", file=verbose_output)
		print(f"Channel map with {len(channels)} entries:\n{channels}\n", file=verbose_output)
		print(f"Size map with {len(sizes)} entries:\n{sizes}\n", file=verbose_output)
		print(f"Base map with {len(bases)} entries:\n{bases}\n", file=verbose_output)

	vidinfo = read_files(args.source, verbose_output, excludes=args.exclude, date_map=dates,
	                     channel_map=channels, size_map=sizes, base_map=bases, dry_run=args.dry_run)

	if not args.dry_run:
		print(f"Found {len(vidinfo)} videos", file=verbose_output)
		writer = csv.writer(args.output, dialect='excel', quoting=csv.QUOTE_ALL)
		writer.writerow(VideoMetadata.csv_header)
		writer.writerows(vidinfo)

	args.output.close()
	verbose_output.close()
