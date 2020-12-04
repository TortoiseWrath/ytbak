import glob
import shlex

import aiopubsub
import argparse
import os
import subprocess
import uuid


def find_attachments(*filenames):
	return {attachment for attachments
	        in [glob.glob(glob.escape(remove_ext(filename)) + '.*') for filename in filenames]
	        for attachment in attachments if attachment not in filenames
	        and ext(attachment) != 'mkv'}


def merge(source_files, audio_files, video_files, subtitle_files, output_filename, pub,
          delete_source=False, delete_json=False, dry_run=False, title=None, keys=None):
	if not keys:
		keys = ['merge']

	attachments = find_attachments(*source_files, *audio_files, *video_files, *subtitle_files)

	created_cover = False
	cover = next((a for a in attachments if ext(a) in ('jpg', 'jpeg')), None)
	cover_source = cover
	if not cover:
		cover = next((a for a in attachments if ext(a) in IMAGE_FILES), None)
		if cover:
			temp_filename = str(uuid.uuid4()) + '.jpg'
			imagick_args = ['convert', cover, temp_filename]
			print(' '.join(map(shlex.quote, imagick_args)))
			if not dry_run:
				result = subprocess.run(imagick_args)
				if result.returncode != 0:
					raise RuntimeError("Got non-zero exit code from convert")
			created_cover = True
			cover_source = cover
			cover = temp_filename
			attachments.add(temp_filename)

	source_files = source_files or []
	audio_files = audio_files or []
	video_files = video_files or []
	subtitle_files = subtitle_files or []

	if os.path.isfile(output_filename):
		i = 1
		while os.path.isfile(f"{remove_ext(output_filename)}_{i}.{ext(output_filename)}"):
			i += 1
		output_filename = f"{remove_ext(output_filename)}_{i}.{ext(output_filename)}"

	output = 'temp.mkv' if output_filename in (source_files + audio_files + video_files +
	                                           subtitle_files) else output_filename

	args = ['mkvmerge', '--no-date', '-o', output]

	if title:
		args += ['--title', title]

	args += [arg for file in attachments for arg in
	         (('--attachment-name', 'cover.jpg', '--attachment-description',
	           os.path.basename(cover_source), '--attach-file', file)
	          if file == cover else ('--attach-file', file))]

	args += source_files
	args += [arg for file in video_files for arg in ('-A', file)]
	if len(audio_files) > 1:
		args += ['-D', '--default-track', '-1:1', audio_files[0]]
		args += [arg for file in audio_files[1:] for arg in ('-D', file)]
	else:
		args += [arg for file in audio_files for arg in ('-D', file)]
	args += [arg for file in subtitle_files for arg in ('-A', '-D', file)]

	files_to_delete = set()
	if delete_source:
		files_to_delete.update(source_files + audio_files + video_files + subtitle_files +
		                       [x for x in attachments if not x.endswith('.json')])
	if delete_json:
		files_to_delete.update([x for x in attachments if x.endswith('.json')])
	if created_cover:
		files_to_delete.add(cover)

	pub.publish(aiopubsub.Key(*keys), ' '.join(map(shlex.quote, args)))
	if not dry_run:
		result = subprocess.run(args)
		if result.returncode != 0:
			raise RuntimeError("Got non-zero exit code from mkvmerge")

	if len(files_to_delete) > 0:
		pub.publish(aiopubsub.Key(*keys), 'rm ' + ' '.join(map(shlex.quote, files_to_delete)))
		if not dry_run:
			result = subprocess.run(['rm', *files_to_delete])
			if result.returncode != 0:
				raise RuntimeError("Got non-zero exit code from rm")

	if output != output_filename:
		pub.publish(aiopubsub.Key(*keys),
		            f"mv {shlex.quote(output)} {shlex.quote(output_filename)}")
		if not dry_run:
			result = subprocess.run(['mv', output, output_filename])
			if result.returncode != 0:
				raise RuntimeError("Got non-zero exit code from mv")


def main():
	parser = argparse.ArgumentParser(
		description="merge files (a/v streams and attachments) into MKV files")
	parser.add_argument('source', nargs='*', help="a/v source file")
	parser.add_argument('-a', '--audio', nargs='*', help="audio source file")
	parser.add_argument('-v', '--video', nargs='*', help="video source file")
	parser.add_argument('-s', '--subs', nargs='*', help="subtitle source file")
	parser.add_argument('-o', '--output', nargs='?', help="output file or directory")
	parser.add_argument('-d', '--delete-source-files', action='store_true',
	                    help="delete source files (excluding json files)")
	parser.add_argument('--delete-source-json', action='store_true', help="delete source json")
	parser.add_argument('--title', nargs='?', help="video title")
	parser.add_argument('-n', '--dry-run', action='store_true', help="dry run")

	args = parser.parse_args()

	hub = aiopubsub.Hub()
	pub = aiopubsub.Publisher(hub, aiopubsub.Key('main'))
	sub = aiopubsub.Subscriber(hub, 'main')
	sub.add_sync_listener(aiopubsub.Key('*'), lambda k, m: print(m))

	source_files = args.source or []
	video_files = args.video or []
	audio_files = args.audio or []
	sub_files = args.subs or []

	all_sources = [*source_files, *video_files, *audio_files, *sub_files]

	if len(all_sources) == 0:
		raise ValueError('No video files')

	output_dir = os.path.dirname(all_sources[0])
	proposed_output_file = all_sources[0] if ext(all_sources[0]) == 'mkv' \
		else remove_ext(all_sources[0]) + '.mkv'
	output_file = output_dir if args.output else proposed_output_file
	if os.path.isdir(output_file):
		output_file = os.path.join(args.output, os.path.basename(proposed_output_file))
	if os.path.isfile(output_file) and output_file not in all_sources:
		raise ValueError(f'File {output_file} already exists')

	merge(source_files or [], audio_files or [], video_files or [], sub_files or [], output_file,
	      delete_source=args.delete_source_files, dry_run=args.dry_run,
	      delete_json=args.delete_source_json, title=args.title, pub=pub)


if __name__ == "__main__":
	main()


def remove_ext(path):
	first = os.path.splitext(path)
	# handle .info.json, .rechat.json, etc.
	if first[1] == '.json':
		second = os.path.splitext(first[0])
		return second[0] if 3 <= len(second[1]) <= 8 else first[0]
	return first[0]


def ext(path):
	first = os.path.splitext(path)
	# handle .info.json, .rechat.json, etc.
	if first[1] == '.json':
		second = os.path.splitext(first[0])
		return second[1][1:] + first[1] if 3 <= len(second[1]) <= 8 else first[1][1:]
	return first[1][1:]


IMAGE_FILES = ['jpg', 'webp', 'png', 'jpeg', 'gif', 'jfif']
