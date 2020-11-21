import csv
import os

IMAGE_FILES = ['jpg', 'webp', 'png', 'jpeg', 'gif']


def remove_ext(path):
	first = os.path.splitext(path)
	# handle .info.json, .rechat.json, etc.
	if first[1] == '.json':
		second = os.path.splitext(path)
		return second[0] if 3 <= len(second[1]) <= 8 else first[0]
	return first[0]


def ext(path):
	first = os.path.splitext(path)
	# handle .info.json, .rechat.json, etc.
	if first[1] == '.json':
		second = os.path.splitext(path)
		return second[1] + first[1] if 3 <= len(second[1]) <= 8 else first[1]
	return first[1]


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
	If none can be determined
	:param video:
	:return: The path where the video should be placed after being downloaded, without extension
	"""
	raise NotImplementedError("Dunno")


def filename_map(videos, rename=True):
	"""
	Create a filename mapping from old paths to new paths according to new_filename,
	excluding file extensions.
	:param videos: List of videos
	:param rename: If false, this only deals with other_path.
	:return: a dictionary
	"""
	path_map = {
		remove_ext(v['Filename']): (new_filename(v) if rename else remove_ext(v['Filename']))
		for v in videos}
	path_map.update({
		remove_ext(v['other_path']): path_map[remove_ext(v['Filename'])]
		for v in videos})
	return path_map


class Downloader:
	def __init__(self, server_map_file, output_file=None, dry_run=False):
		"""
		Initialize the downloader.
		:param server_map_file: A server map file opened for reading
		:param output_file: An output file opened for writing (optional)
		:param dry_run: Whether to do a dry run
		"""
		self.__read_server_map(server_map_file)
		self.output_file = output_file
		self.dry_run = dry_run

		if not os.path.exists('temp'):
			os.makedirs('temp')

		self.running_jobs = []

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

	def __create_filter_files(self, videos, include_videos=True, include_thumbnails=True,
	                          include_metadata=False):
		"""
		Create filter files to select files from rsync.
		:param include_metadata: Whether to include json files as well as video files
		:param include_thumbnails: Whether to include thumbnail files as well as video files
		:param videos: Videos to download
		:return: dictionary mapping server name to path to relevant file
		"""
		raise NotImplementedError("Can't create filter file")

	def run_rclone(self, server, destination, action, filter_file, dry_run=False):
		raise NotImplementedError("Don't know how to rclone.")

	def download(self, videos, download=True, delete=False, dry_run=False, destination='.',
	             job_name=None):
		"""
		Download videos
		:param videos: Videos to download
		:param download: Whether to perform the download
		:param delete: Whether to delete the files from the server
		:param dry_run: Whether to perform a dry run
		:param job_name: job name (optional)
		:param destination: download destination
		:return: a future that completes when downloads are complete
		"""
		if download:
			rclone_action = 'move' if delete else 'copy'
			filter_files = self.__create_filter_files(videos, include_metadata=not delete)
			for server, filter_file in filter_files.items():
				for rclone_server in self.server_map[server]:
					self.run_rclone(rclone_server, destination, rclone_action, filter_file,
					                dry_run=dry_run)
			if delete:
				# Get just metadata files, which should not be deleted
				metadata_filter_files = self.__create_filter_files(videos, include_videos=False,
				                                                   include_thumbnails=False,
				                                                   include_metadata=True)
				for server, filter_file in metadata_filter_files.items():
					for rclone_server in self.server_map[server]:
						self.run_rclone(rclone_server, destination, 'copy', filter_file,
						                dry_run=dry_run)
		elif delete:
			filter_files = self.__create_filter_files(videos, include_metadata=False)
			for server, filter_file in filter_files.items():
				for rclone_server in self.server_map[server]:
					self.run_rclone(rclone_server, 'delete', filter_file, dry_run=dry_run)
			raise NotImplementedError("No deleting.")

	def merge_and_rename(self, videos, add_attachments=True, merge=True, rename=True, dry_run=False,
	                     job_name=None):
		"""
		Merge and rename downloaded videos according to the rules suggested by videos
		:param videos:
		:param add_attachments: Whether to add attachments to the downloaded file
		:param merge: Whether to merge downloaded video files according to the "result" column
		:param rename: Whether to rename files to new_filename(video)
		:param dry_run: Whether to perform a dry run
		:param job_name: job name (optional)
		:return: 
		"""
		path_map = filename_map(videos, rename=rename)

	def download_and_merge(self, videos, download=True, delete=False, add_attachments=True,
	                       rename=True, job_name=None):
		"""
		Download only those videos that require stream merging, and merge the streams
		:param videos: A list of video dictionaries
		:param download: Whether to perform the download
		:param delete: Whether to delete the files from the server
		:param add_attachments: Whether to add json and image files as attachments in mkv
		:param rename: Whether to rename files to new_filename(video)
		:param job_name: Job name (optional)
		:return: a job?  # TODO: what
		"""
		raise NotImplementedError("No downloading and especially no merging.")


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
	for expected_key in 'Server', 'Filename', 'Size', 'Date', 'Duration', 'Group', 'Series', \
	                    'Episode', 'Output Title', 'Part', 'result', 'other_path', 'other_server':
		if expected_key not in videos[0]:
			raise ValueError(f"Did not find key {expected_key} in vidinfo csv. values: {videos[0]}")
	return videos


def filter_videos(all_videos, *expected_result_classes):
	return [x for x in all_videos if x['result'].split('_')[0] in expected_result_classes]
