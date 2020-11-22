import os


def get_input_files(directory):
	"""
	Get a list of files in the directory
	:param directory: The path to the directory
	:return: list of files
	"""
	return [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
