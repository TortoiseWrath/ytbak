import csv
import os

IMAGE_FILES = ['jpg', 'webp', 'png', 'jpeg', 'gif']

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
	:param video:
	:return: The path where the video should be placed after being downloaded, without extension
	"""
	raise NotImplementedError("Dunno")


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

	def spawn_rclone(self, arguments, dry_run=False):
		raise NotImplementedError("Don't know how to rclone.")

	def create_filter_files(self, videos, include_thumbnails=True, include_metadata=False):
		"""
		Create filter files to select files from rsync.
		:param include_metadata: Whether to include json files as well as video files
		:param include_thumbnails: Whether to include thumbnail files as well as video files
		:param videos: Videos to download
		:return: dictionary mapping server name to path to relevant file
		"""
		raise NotImplementedError("Can't create filter file")

	def download(self, videos, download=True, delete=False, add_attachments=True, rename=True,
	             dry_run=False, job_name=None):
		"""
		Download videos
		:param videos: Videos to download
		:param download: Whether to perform the download
		:param delete: Whether to delete the files from the server
		:param add_attachments: Whether to add json and image files as attachments in mkv
		:param rename: Whether to rename files to new_filename(video)
		:param dry_run: Whether to perform a dry run
		:param job_name: job name (optional)
		:return: a future that completes when everything is done
		"""
		if download:
			# Perform the downloading.
			rclone_action = 'move' if delete else 'copy'
			filter_files = self.create_filter_files(videos, include_metadata=not delete)
			if delete:
				# Create a second thread for just metadata files, which should not be deleted
				raise NotImplementedError()
			raise NotImplementedError("No downloading.")
			if add_attachments:
				# Monitor rclone instance and wait for files to get downloaded
				# When mkv files are downloaded, rename and add to the job "downloaded" list
				# When non-mkv files are downloaded, convert and add to the job "downloaded" list
				# When videos are added to the "downloaded" list, check the "pending_attachments"
				# list for pending attachments. If there are any, merge them.
				# When attachments are downloaded, check whether the corresponding video file has
				# been downloaded. If so, merge the attachment; otherwise, add them to pending.
				raise NotImplementedError("No attaching.")
		if delete and not download:
			raise NotImplementedError("No deleting.")

	def download_and_merge(self, videos, download=True, delete=False, add_attachments=True,
	                       rename=True):
		"""
		Download only those videos that require stream merging, and merge the streams
		:param videos: A list of video dictionaries
		:param download: Whether to perform the download
		:param delete: Whether to delete the files from the server
		:param add_attachments: Whether to add json and image files as attachments in mkv
		:param rename: Whether to rename files to new_filename(video)
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
	raise NotImplementedError("No reading.")


def filter_videos(all_videos, *expected_result_classes):
	return [x for x in all_videos if x['result'].split('_')[0] in expected_result_classes]
