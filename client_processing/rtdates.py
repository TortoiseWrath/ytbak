import argparse
import csv
import os
import re
import sys

# Scan files for URLs in the format:
# https://roosterteeth.com/watch/rouletsplay-2020-10-7
# and match them with subsequent dates in the format mm/dd/yyyy
# Create a csv file with: video_id,yyyy-mm-dd

url_pattern = re.compile(r'"https://roosterteeth\.com/watch/([^"]+)"')
date_pattern = re.compile(r"(\d\d)/(\d\d)/(20\d\d)")


def read_dates(filename, stdout):
	"""Read all dates in a file. Return dict mapping video id to date"""
	print(f"Reading file: {filename}", file=stdout)
	videos = {}

	lines = 0

	video_id = None
	with open(filename, encoding='cp1252') as file:
		for line in file:
			lines += 1
			url_match = url_pattern.search(line)
			if lines < 2700:
				continue
			if url_match:
				matched_id = url_match.group(1)
				if video_id is not None and video_id != matched_id:
					print(
						f"Warning: no date found for {video_id} before {matched_id}",
						file=sys.stderr)
				video_id = matched_id
			else:
				m = date_pattern.search(line)
				if m:
					videos[video_id] = f'{m.group(3)}{m.group(1)}{m.group(2)}'
					video_id = None
	# TODO: If video_id is on the same line as its date, we will have a bad time

	print(f"Read {lines} lines and got {len(videos)} videos from file {filename}", file=stdout)
	return videos


def write_file(dates, destination):
	"""Write video-date mapping to a csv file"""
	writer = csv.writer(destination)
	for video_id, video_date in dates.items():
		writer.writerow([video_id, video_date])


def convert_files(files, destination, stdout):
	"""Convert list of input files"""
	for filename in files:
		try:
			videos = read_dates(filename, stdout)
			print(f"Writing {len(videos)} videos from file {filename} to output file", file=stdout)
			write_file(videos, destination)
		except IOError as error:
			print(f"Failed to open file {filename}!", error, file=sys.stderr)

	print(f"Processed {len(files)} files", file=stdout)


if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description="Match RoosterTeeth.com video URLs with subsequent upload dates in input files")
	parser.add_argument('-o', '--output', help="Output file (csv)", nargs='?',
	                    type=argparse.FileType('w'), default=sys.stdout)
	parser.add_argument('input', nargs='+', help="Input file (html)")
	parser.add_argument('-v', '--verbose', help="Increase verbosity", action='store_true')
	args = parser.parse_args()

	if args.verbose:
		if args.output == sys.stdout:
			logfile = sys.stdout
		else:
			logfile = sys.stderr
	else:
		logfile = open(os.devnull, 'w')

	exit_code = 0

	try:
		convert_files(args.input, args.output, logfile)
	except IOError as e:
		print(f"Fatal I/O Error!", e, file=sys.stderr)
		exit_code = 1

	args.output.close()
	logfile.close()
	exit(exit_code)
