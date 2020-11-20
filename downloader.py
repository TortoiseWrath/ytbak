import csv


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


# Downloader model
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

	def download(self, videos, download=True, delete=False, add_attachments=True, rename=True):
		raise NotImplementedError("No downloading.")

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
