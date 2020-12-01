import unicodedata

import aiopubsub
import asyncio
import csv
import os
import re
import subprocess
import uuid
from humanize import naturalsize

from merge import merge as merge_videos, remove_ext, ext, IMAGE_FILES


def _create_filter_files(videos, include_videos=True, include_thumbnails=True,
                         include_metadata=False):
	"""
	Create filter files to select files from rsync.
	:param include_metadata: Whether to include json files as well as video files
	:param include_thumbnails: Whether to include thumbnail files as well as video files
	:param videos: Videos to download
	:return: dictionary mapping server name to path to relevant file
	"""
	filter_map = {}  # server -> list of filters
	add_extensions = IMAGE_FILES.copy() if include_thumbnails else []
	if include_metadata:
		add_extensions.append('*.json')

	for v in videos:
		extensions = add_extensions.copy()
		if include_videos:
			extensions.append(ext(v['Filename']))
		if v['Server'] not in filter_map:
			filter_map[v['Server']] = []
		filter_map[v['Server']].append(
			f"/{re.escape(remove_ext(v['Filename']))}.{{{','.join(extensions)}}}\n")
		if v['other_server']:
			if v['other_server'] not in filter_map:
				filter_map[v['other_server']] = []
			filter_map[v['other_server']].append(
				f"/{re.escape(remove_ext(v['other_path']))}.{{{','.join(extensions)}}}\n")

	filter_files = {}  # server -> filename
	for server, filters in filter_map.items():
		filename = 'temp/' + str(uuid.uuid4())
		filter_files[server] = filename
		with open(filename, 'w') as file:
			file.writelines(filters)

	return filter_files


class Downloader:
	def __init__(self, server_map_file, hub, prefix, output_dir='.', output_file=None,
	             dry_run=False):
		"""
		Initialize the downloader.
		:param server_map_file: A server map file opened for reading
		:param hub: Message hub
		:param prefix: Message prefix
		:param output_dir: where to download to
		:param output_file: An output file opened for writing
		:param dry_run: Whether to do a dry run
		"""
		self.__read_server_map(server_map_file)
		self.output_file = csv.writer(output_file)
		self.dry_run = dry_run
		self.output_dir = output_dir
		self.publisher = aiopubsub.Publisher(hub, aiopubsub.Key(prefix))
		if not os.path.exists('temp'):
			os.makedirs('temp')

	def __read_server_map(self, file):
		"""
		Read the one-to-many server map
		:param file: A file opened for reading
		:return: Server map dictionary
		"""
		server_map = {}
		reader = csv.reader(file)
		for row in reader:
			if row[0] not in server_map:
				server_map[row[0]] = []
			server_map[row[0]].append(row[1])
		self.server_map = server_map

	def __pub(self, message, keys):
		self.publisher.publish(aiopubsub.Key(*keys), message)

	async def run_rclone(self, server, destination, action, filter_file, keys, video_sizes=None):
		"""
		Run rclone with the given parameters.
		Sends messages corresponding to total
		:param server: Which server to connect to
		:param destination: Destination to which to download
		:param action: What to do
		:param filter_file: Filter file
		:param video_sizes: Video size map (optional)
		:param keys: message keys
		"""
		command = ['rclone', action, '-vvn' if self.dry_run else '-vv', '--include-from',
		           filter_file, server]
		if action != 'delete':
			command.append(destination)
		self.__pub(self.NewTaskMessage(command=' '.join(command)), keys)

		p = await asyncio.create_subprocess_exec(*command, stderr=asyncio.subprocess.PIPE)

		while True:
			data = await p.stderr.readline()
			if data:
				line = data.decode('utf-8').rstrip()

				log_level = None
				event = None
				file = None
				items = None
				size = None
				try:
					log_level = line[:line.index(': ')][-7:].strip()
					event = line[line.rfind(': ') + 2:]
					file = line[line.index(': ') + 2:line.rfind(': ')]
				except ValueError:
					pass

				if log_level and (event.endswith('--dry-run')
				                  or event.endswith('skipping')  # Already downloaded; add to totals
				                  or (event == 'Deleted' and action == 'delete')
				                  or event.startswith('Copied')
				                  or event.startswith('Multi-thread Copied')):
					# Something significant happened
					extension = ext(file)
					if extension not in IMAGE_FILES and not extension.endswith('json'):
						# Something happened to a video file so add it to the totals
						items = 1
						if video_sizes:
							size = video_sizes[file]
				elif log_level == 'DEBUG':
					# Ignore the unimportant debug message
					continue

				# Send a message with deltas for total progress where applicable, plus rclone output
				self.__pub(self.ProgressMessage(line, items, size), keys)
			elif p.returncode is None:
				await asyncio.sleep(10)  # Process is paused; wait for it to come back
			else:
				break

		await p.wait()

		self.__pub(self.CompletedMessage(command=' '.join(command), exitcode=p.returncode), keys)
		if p.returncode != 0:
			raise RuntimeError(f'rclone exited with return code {p.returncode}')

	async def download(self, videos, keys, download=True, delete=False):
		"""
		Download videos
		:param videos: Videos to download
		:param keys: message keys
		:param download: Whether to perform the download
		:param delete: Whether to delete the files from the server
		"""
		# TODO: use locale.atoi (wasn't working)
		size_map = {v['Filename']: int(v['Size'].strip().replace(',', '')) for v in videos if
		            v['Size']} if download else None

		self.__pub(self.NewTaskMessage(
			total_items=len(videos), total_bytes=sum(size_map.values()) if size_map else None),
			keys)

		tasks = []
		if download:
			rclone_action = 'move' if delete else 'copy'
			filter_files = _create_filter_files(videos, include_metadata=not delete)
			for server, filter_file in filter_files.items():
				for rclone_server in self.server_map[server]:
					tasks.append(
						self.run_rclone(rclone_server, self.output_dir, rclone_action, filter_file,
						                video_sizes=size_map, keys=(*keys, f't{len(tasks)}')))
			if delete:
				# Get just metadata files, which should not be deleted
				metadata_filter_files = _create_filter_files(
					videos, include_videos=False, include_thumbnails=False, include_metadata=True)
				for server, filter_file in metadata_filter_files.items():
					for rclone_server in self.server_map[server]:
						tasks.append(
							self.run_rclone(rclone_server, self.output_dir, 'copy', filter_file,
							                video_sizes=size_map, keys=(*keys, f't{len(tasks)}')))
		elif delete:
			filter_files = _create_filter_files(videos, include_metadata=False)
			for server, filter_file in filter_files.items():
				for rclone_server in self.server_map[server]:
					tasks.append(
						self.run_rclone(rclone_server, None, 'delete', filter_file,
						                keys=(*keys, f't{len(tasks)}')))

		await asyncio.gather(*tasks)
		self.__pub(self.CompletedMessage(), keys)

	async def merge_and_rename(self, videos, keys):
		"""
		Merge and rename downloaded videos according to the rules suggested by videos
		:param videos: list of videos
		:param keys: message keys
		"""
		# if not (merge or rename):
		# 	return
		#
		# if merge and not rename:
		# 	raise ValueError("Cannot merge but not rename")
		#
		# if rename and not merge:
		# 	self.__pub(self.NewTaskMessage(total_items=len(videos)), keys)
		# 	for video in videos:
		# 		destination = new_filename(video) + '.' + ext(video['Filename'])
		# 		self.__pub(f"mv {shlex.quote(video['Filename'])} {shlex.quote(destination)}", keys)
		# 		if not self.dry_run:
		# 			result = subprocess.run(['mv', video['Filename'], destination])
		# 			if result.returncode != 0:
		# 				raise RuntimeError("Got non-zero exit code from mv")
		# 		self.output_file.writerow([video['Filename'], destination])
		# 		self.__pub(self.ProgressMessage(video['Filename'], processed_items=1), keys)
		# 	self.__pub(self.CompletedMessage(), keys)
		# 	return

		destinations = {}
		for video in videos:
			target = new_filename(video)
			if target not in destinations:
				destinations[target] = []
			destinations[target].append(video)

		self.__pub(self.NewTaskMessage(total_items=len(destinations)), keys)

		for target, sources in destinations.items():
			if len(sources):
				av_files = [self.output_dir + '/' + x['Filename'] for x in sources if
				            x['result'].startswith('keep') or x['result'] == 'audio+video']
				video_files = [self.output_dir + '/' + x['Filename'] for x in sources if
				               x['result'] in ['video', 'video+subs']]
				audio_files = [self.output_dir + '/' + x['Filename'] for x in sources if
				               x['result'] in ['audio', 'audio+subs']] \
				              + video_files  # include all audio tracks
				merge_videos(
					source_files=av_files,
					audio_files=audio_files,
					video_files=video_files,
					subtitle_files=[self.output_dir + '/' + x['Filename'] for x in sources if
					                x['result'] in ['subs', 'audio+subs', 'video+subs']],
					output_filename=self.output_dir + '/' + target + '.mkv',
					delete_source=True,
					delete_json=True,  # json will not be deleted from server, only destination
					dry_run=self.dry_run,
					title=sources[0]['Output Title'],
					pub=self.publisher, keys=[*keys, 'merge']
				)
				self.output_file.writerows([[x['Filename'], target + '.mkv'] for x in sources])
			self.__pub(self.ProgressMessage("Merged: " + target, processed_items=1),
			           [*keys, 'merge'])

		# ugly hack to get rid of empty directories created in this process
		subprocess.run(['find', self.output_dir, '-type', 'd', '-empty', '-delete'])

		self.__pub(self.CompletedMessage(), keys)

	async def download_and_merge(self, videos, keys, download=True, delete=False):
		"""
		Download videos, then merge and rename
		:param videos: A list of video dictionaries
		:param download: Whether to perform the download
		:param keys: message keys
		:param delete: Whether to delete the files from the server
		:param add_attachments: Whether to add json and image files as attachments in mkv
		:param merge: Whether to merge downloaded video files according to the "result" column
		:param rename: Whether to rename files to new_filename(video)
		"""

		await self.download(videos, [*keys, 'download'], download, delete)
		if download:
			await self.merge_and_rename(videos, [*keys, 'merge'])

	class NewTaskMessage:
		def __init__(self, command=None, total_items=None, total_bytes=None):
			self.command = command
			self.total_items = total_items
			self.total_bytes = total_bytes

		def __str__(self):
			if self.total_bytes:
				return f"processing {self.total_items or ''} items totaling {naturalsize(self.total_bytes)}"
			elif self.total_items:
				return f"processing {self.total_items} items"
			return f"started: {self.command}"

	class ProgressMessage:
		def __init__(self, update_message, processed_items=None, processed_bytes=None):
			self.items = processed_items
			self.bytes = processed_bytes
			self.message = update_message

		def __str__(self):
			return self.message

	class CompletedMessage:
		def __init__(self, command=None, exitcode=None):
			self.command = command
			self.exitcode = exitcode

		def __str__(self):
			return f"{self.command.split()[0]} exited with status {self.exitcode}" if self.command \
				else "task completed"


def read_source_file(filename, tsv=False):
	"""
	Read a source file into a list of video dictionaries
	:param filename: A file opened for reading
	:param tsv: The type of file: false for UTF-8 CSV, true for UTF-16 TSV
	:return: A list of video dictionaries
	"""
	with open(filename, 'r', newline='',
	          encoding='utf-16' if tsv else 'utf-8') as csvfile:
		reader = csv.DictReader(csvfile, dialect='excel-tab' if tsv else 'excel')
		videos = list(reader)
	for expected_key in ('Server', 'Filename', 'Size', 'Date', 'Duration', 'Group', 'Series',
	                     'Episode', 'Output Title', 'Part', 'result', 'other_path', 'other_server'):
		if expected_key not in videos[0]:
			raise ValueError(f"Did not find key {expected_key} in vidinfo csv. values: {videos[0]}")
	return videos


def filter_videos(all_videos, *expected_result_classes):
	return [x for x in all_videos if x['result'].split('_')[0] in expected_result_classes]


def new_filename(video):
	"""
	Determine the appropriate output filename for a video. It can be in any of these formats:
	{Group}/{Series}/{Date}
	{Group}/{Series}/{Date} - {Output Title}
	{Group}/{Series}/{Date} - Episode {Episode}
	{Group}/{Series}/{Date} - Episode {Episode} - {Output Title}
	{Group}/{Series}/{Date} - Part {Part}
	{Group}/{Series}/{Date} - {Output Title} - Part {Part}
	{Group}/{Series}/{Date} - Episode {Episode} - Part {Part}
	{Group}/{Series}/{Date} - Episode {Episode} - {Output Title} - Part {Part}
	{Group}/{Series}/{Output Title} (if Output Title starts with S##E##)
	{Group}/{Series}/{Output Title} - Part {Part} (if Output Title starts with S##E##)
	{Group}/{Date}
	{Group}/{Date} - {Output Title}
	{Group}/{Date} - Episode {Episode}
	{Group}/{Date} - Episode {Episode} - {Output Title}
	{Group}/{Date} - Part {Part}
	{Group}/{Date} - {Output Title} - Part {Part}
	{Group}/{Date} - Episode {Episode} - Part {Part}
	{Group}/{Date} - Episode {Episode} - {Output Title} - Part {Part}
	It does NOT include the file extension!
	If none can be determined the filename is unchanged
	:param video:
	:return: The path where the video should be placed after being downloaded, without extension
	"""
	se_format = False if not video['Output Title'] else (
			video['Series'] and re.match(r'^S\d{2,}E\d{2,} ', video['Output Title']))
	if not (video['Group'] and (video['Date'] or se_format)):
		# Cannot determine an appropriate output filename
		return remove_ext(video['Filename'])

	output_filename = video['Group'] + '/'
	if se_format:
		output_filename += sanitize(video['Output Title'])
	else:
		if video['Series']:
			output_filename += video['Series'] + '/'

		date = video['Date'].strip()
		if not re.match(r'^\d{8}$', date):
			return remove_ext(video['Filename'])
		output_filename += f"{date[0:4]}-{date[4:6]}-{date[6:8]}"

		if video['Episode']:
			output_filename += f" - Episode {sanitize(video['Episode'])}"

		if video['Output Title']:
			output_filename += f" - {sanitize(video['Output Title'])}"

	if video['Part']:
		output_filename += f" - Part {sanitize(video['Part'])}"
	return output_filename


def sanitize(input):
	return ''.join(c if c not in r'<>:"/\|?*' and '\u0020' <= c <= '\uFFFF' else (
		' -' if c == ':' else '_') for c in unicodedata.normalize('NFC', input)).strip()
