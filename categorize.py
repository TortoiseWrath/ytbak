import argparse
import csv
import sys


# https://en.wikibooks.org/wiki/Algorithm_Implementation/Strings/Longest_common_substring#Python
def longest_common_substring(s1, s2):
	m = [[0] * (1 + len(s2)) for i in range(1 + len(s1))]
	longest, x_longest = 0, 0
	for x in range(1, 1 + len(s1)):
		for y in range(1, 1 + len(s2)):
			if s1[x - 1] == s2[y - 1]:
				m[x][y] = m[x - 1][y - 1] + 1
				if m[x][y] > longest:
					longest = m[x][y]
					x_longest = x
			else:
				m[x][y] = 0
	return s1[x_longest - longest: x_longest]


def read_vidinfo(filename):
	with open(filename, 'r', newline='', encoding='cp1252') as csvfile:
		reader = csv.DictReader(csvfile)
		videos = list(reader)
	for expected_key in 'Website', 'Size', 'ID', 'Title', 'Date', 'Duration', 'Subtitles', \
	                    'Height', 'Total bitrate', 'Group', 'Series', 'Episode', 'Output Title', \
	                    'Part', 'Flag':
		if expected_key not in videos[0]:
			raise ValueError(f"Did not find key {expected_key} in vidinfo csv")
	return videos


def read_alive_list(filename):
	with open(filename, 'r') as file:
		return set(file.read().splitlines())


def process_vidinfo(input_vidinfo, alivelist):
	"""
	Process the vidinfo file, adding columns to indicate what should be done with the video.

	The column "result" decides what to do with the file.

	Videos are assumed to be identical if all of the following are true:
	* They were uploaded within 1 day of each other
	* Their length is within 5% + max(45 seconds, 10%) of the shorter length
	* Longest common substring is more than half of longer title

	Preferred sources are found by:
	1. File exists (size is not blank)
	2. Video height
	3. Bitrate
	4. Default to preferring YT video if before 2019-01-01, else RT video

	The result is "inspect" if:
	* Flag already exists in flag column
	* There are no matching videos with nonempty size
	* There is more than 1 yt video or more than 1 rt video

	If YouTube > 2019-10-01 is preferred, the results are "audio" and "video"
	If one has subtitles and the other doesn't, the results are "subs" and "audio+video"
	If both apply, the results are "audio+subs" and "video" or "audio" and "video+subs"
	If the size is blank, the result is "ignore"
	Otherwise, the results are "keep" and "delete"

	The column "alive" says whether the video is still up on YT.

	The column "original_row" is the original row number, in case you need to sort back.

	The column "yt_id" is the id of a matching youtube video
	The column "rt_id" is the id of a matching rt video

	:param input_vidinfo: list of dicts representing a vidinfo file
	:param alivelist: set of alive videos
	:return: list of dicts representing a vidinfo file, with more columns
	"""
	results = []
	processed_indices = set()

	# Sort by dates, ascending
	input_vidinfo = sorted(input_vidinfo, key=lambda x: x['Date'])

	for i in range(len(input_vidinfo)):
		# Skip rows that matched a previous video
		if i in processed_indices:
			continue

		current = input_vidinfo[i]
		current['original_row'] = i
		matching_rows = [current]

		# Check for a missing date
		if not current['Date'] or int(current['Date']) < 20040101:
			current['result'] = 'inspect'
			results.append(current)
			continue

		# Compare to all videos between the next one and the last video tomorrow
		j = i
		while True:
			j = j + 1
			if j > len(input_vidinfo) - 1:
				break
			if j in processed_indices:
				continue
			compare = input_vidinfo[j]

			# Check for a date mismatch
			if compare['Date'] and int(compare['Date']) > int(current['Date']) + 1:
				break

			# Check for a length mismatch
			len1 = int(current['Duration'])
			len2 = int(compare['Duration'])
			min_length = min(len1, len2)
			max_length = max(len1, len2)
			if max_length > min_length * 1.05 + max(45., min_length / 10):
				continue

			# Check for a title mismatch
			title_match = longest_common_substring(current['Title'], compare['Title'])
			if len(title_match) < max(len(current['Title']), len(compare['Title'])) // 2:
				continue

			# No mismatch = same video
			compare['original_row'] = j
			matching_rows.append(compare)
			processed_indices.add(j)

		# Remove any rows with the same server, path, size
		matching_rows = list(
			{f"{x['Server']}/{x['Filename']}/{x['Size']}": x for x in matching_rows}.values())

		# Check for inspection conditions
		flag_already_exists = sum(1 for x in matching_rows if x['Flag'])
		existing_videos = [x for x in matching_rows if x['Size']]
		youtube_videos = [x for x in existing_videos if x['Website'] == 'youtube']
		roosterteeth_videos = [x for x in existing_videos if x['Website'] == 'RoosterTeeth']
		if flag_already_exists or not existing_videos or len(youtube_videos) > 1 or len(
				roosterteeth_videos) > 1:
			results += [x | {'result': 'inspect'} for x in matching_rows]
			continue

		youtube_video = youtube_videos[0] if youtube_videos else None
		roosterteeth_video = roosterteeth_videos[0] if roosterteeth_videos else None
		values = {'alive': youtube_video['ID'] in alivelist if youtube_video else None,
		          'yt_id': youtube_video['ID'] if youtube_video else None,
		          'rt_id': roosterteeth_video['ID'] if roosterteeth_video else None}
		non_existing_videos = [x | {'result': 'ignore'} for x in matching_rows if
		                       not x['Size']]

		# If only one or the other exists, our decision is easy
		if not youtube_video or not roosterteeth_video:
			video = youtube_video if youtube_video else roosterteeth_video
			video['result'] = 'keep'
			results += [x | values for x in non_existing_videos]
			results.append(video | values)
			continue

		earlier_date = min(int(youtube_video['Date']), int(roosterteeth_video['Date']))
		values['Date'] = earlier_date

		# Default preference
		youtube_preferred = earlier_date < 20180101

		# Compare bitrates
		if float(youtube_video['Total bitrate']) < float(roosterteeth_video['Total bitrate']):
			youtube_preferred = False
		elif float(roosterteeth_video['Total bitrate']) < float(youtube_video['Total bitrate']):
			youtube_preferred = True

		# Compare video heights
		if youtube_video['Height'] < roosterteeth_video['Height']:
			youtube_preferred = False
		elif roosterteeth_video['Height'] > roosterteeth_video['Height']:
			youtube_preferred = True

		# Check for YT preferred after 20191001 to avoid censored audio
		merge_videos = youtube_preferred and earlier_date >= 20191001

		# Video A has preferred video feed; video B may have preferred other stuff
		video_a = youtube_video if youtube_preferred else roosterteeth_video
		video_b = roosterteeth_video if youtube_preferred else youtube_video
		subs_from_a = int(video_a['Subtitles']) > int(video_b['Subtitles'])
		subs_from_b = int(video_b['Subtitles']) > int(video_a['Subtitles'])

		if merge_videos:
			video_a['result'] = 'video+subs' if subs_from_a else 'video'
			video_b['result'] = 'audio+subs' if subs_from_b else 'audio'
		else:
			video_a['result'] = 'audio+video' if subs_from_b else 'keep'
			video_b['result'] = 'subs' if subs_from_b else 'delete'

		# Merge manually entered metadata
		for metadata_key in ['Group', 'Series', 'Episode', 'Output Title', 'Part', 'Flag']:
			values[metadata_key] = video_a[metadata_key] or video_b[metadata_key] or next(
				(x[metadata_key] for x in non_existing_videos if x[metadata_key]), None)

		results += [youtube_video | values, roosterteeth_video | values]
		results += [x | values for x in non_existing_videos]

	return results


def write_vidinfo(vidinfo_dict, csvfile):
	fieldnames = list(vidinfo_dict[0])
	for extra_name in 'rt_id', 'yt_id', 'alive', 'original_row', 'result':
		if extra_name not in fieldnames:
			fieldnames.append(extra_name)
	writer = csv.DictWriter(csvfile, fieldnames)
	writer.writeheader()
	writer.writerows(vidinfo_dict)


if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description="Identify preferable versions of RoosterTeeth videos in a processed vidinfo csv file")
	parser.add_argument('source', help="vidinfo csv file", nargs='?')
	parser.add_argument('-o', '--output', help="output file", nargs='?',
	                    type=argparse.FileType('w'), default=sys.stdout)
	parser.add_argument('-a', '--alive-list', help="file listing still-alive video ids")
	args = parser.parse_args()

	vidinfo = read_vidinfo(args.source)
	alive_videos = read_alive_list(args.alive_list)
	vidinfo = process_vidinfo(vidinfo, alive_videos)
	write_vidinfo(vidinfo, args.output)

	args.output.close()
