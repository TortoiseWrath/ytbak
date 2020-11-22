from collections import OrderedDict

import aiopubsub
import curses
from humanize import naturalsize
from math import floor
from textwrap import wrap

from downloader import Downloader


# From https://github.com/chrisfleming/python-scrolling-pad/blob/master/infinite_pad.py
class InfinitePad():
	def __init__(self, screen, height, width, y_start, x_start):
		self.screen = screen
		self.height = height
		self.width = width
		self.y_start = y_start
		self.x_start = x_start

		self.pad_top = 0
		self.pad_pos = 0

		self.pad = curses.newpad(self.height * 3, self.width)

	def write(self, message):
		for line in message.split('\n'):
			if self.pad_pos < self.height:
				self.pad.addnstr(self.pad_pos, 0, line, self.width)
			else:
				# We write the string twice, one to the current vie
				# and once to the top of the bad for when we reset.
				pad_b = self.pad_pos - self.height
				self.pad.addnstr(self.pad_pos, 0, line, self.width)
				self.pad.addnstr(pad_b, 0, line, self.width)

			# We should probably do this only when we have written everything
			self.pad.refresh(self.pad_top, 0,
			                 self.y_start, self.x_start,
			                 self.y_start + self.height - 1, self.x_start + self.width)

			if self.pad_pos == (self.height * 2) - 1:
				# Reset
				self.pad_top = 1
				self.pad_pos = self.height
			elif self.pad_pos >= self.height - 1:
				self.pad_pos = self.pad_pos + 1
				self.pad_top = (self.pad_pos - self.height) + 1
			else:
				self.pad_top = 0
				self.pad_pos = self.pad_pos + 1


class DownloadView:
	def __init__(self, logfile, hub):
		self.logfile = logfile
		self.hub = hub
		self.log_lines = []
		self.jobs = OrderedDict()

		self.stdscr = curses.initscr()
		curses.noecho()
		curses.cbreak()
		curses.curs_set(False)
		self.stdscr.keypad(True)

		self.log_pad = None
		self.progress_window = None
		self.log_height = None
		self.progress_height = None
		self.width = None
		self.height = None
		self.create_windows()

		self.log_subscriber = aiopubsub.Subscriber(hub, 'logger')
		self.log_subscriber.add_sync_listener(aiopubsub.Key('*'), self.log)

		self.job_subscriber = aiopubsub.Subscriber(hub, 'job_monitor')
		self.job_subscriber.add_sync_listener(aiopubsub.Key('*'), self.update_jobs)

	def __del__(self):
		curses.nocbreak()
		self.stdscr.keypad(False)
		curses.echo()
		curses.endwin()
		print('\n'.join(self.log_lines))
		print('; '.join([f"{'.'.join(key)}: {job}" for key, job in self.jobs.items()]))

	def update_jobs(self, key, message):
		if isinstance(message, Downloader.ProgressMessage):
			return
		if isinstance(message, Downloader.NewTaskMessage) and (
				message.total_items or message.total_bytes):
			self.jobs[key] = self.Job(key, self.hub, message.total_items, message.total_bytes, self)
		elif isinstance(message, Downloader.CompletedMessage):
			self.jobs.pop(key, None)
		self.refresh_progress_window()

	def log(self, key, message):
		log_message = f"[{'.'.join(key)}] {message}"
		print(log_message, file=self.logfile)
		self.log_lines.append(log_message)
		self.log_pad.write('\n'.join(wrap(log_message, self.width)))

	def create_windows(self):
		self.height, self.width = self.stdscr.getmaxyx()
		self.progress_height = max(4, len(self.jobs) + 1)
		self.log_height = self.height - self.progress_height
		self.log_pad = InfinitePad(self.stdscr, self.log_height, self.width, self.progress_height,
		                           0)
		self.log_pad.write('\n'.join(['\n'.join(wrap(x, self.width))
		                              for x in self.log_lines[-self.log_height:]]))
		self.progress_window = curses.newwin(
			self.progress_height, self.width, 0, 0)
		self.refresh_progress_window()

	def refresh_progress_window(self):
		if self.need_new_windows():
			self.create_windows()
		else:
			self.progress_window.clear()
		for key, job in self.jobs.items():
			self.progress_window.addstr(f"{'.'.join(key)}: {job}")
		self.progress_window.refresh()

	def need_new_windows(self):
		return (not self.log_pad or not self.progress_window or
		        (self.height, self.width) != self.stdscr.getmaxyx() or
		        self.progress_height < len(self.jobs))

	class Job:
		def __init__(self, key, hub, total_items, total_bytes, view):
			self.total_items = total_items
			self.total_bytes = total_bytes
			self.processed_items = 0
			self.processed_bytes = 0
			self.subscriber = aiopubsub.Subscriber(hub, '.'.join(key))
			self.subscriber.add_sync_listener(aiopubsub.Key(*key, '*'), self.update_progress)
			self.view = view

		# def __del__(self):
		# 	await self.subscriber.remove_all_listeners()

		def __str__(self):
			percent = floor((self.processed_bytes / self.total_bytes if self.total_bytes
			                 else self.processed_items / self.total_items) * 100)
			string = f"{percent}% - "
			if self.total_items:
				string += f"{self.processed_items}/{self.total_items}"
				if self.total_bytes:
					string += ', '
			if self.total_bytes:
				string += f"{naturalsize(self.processed_bytes)} / {naturalsize(self.total_bytes)}"
			return string

		def update_progress(self, key, message):
			if not isinstance(message, Downloader.ProgressMessage):
				return
			if message.items:
				self.processed_items += message.items
			if message.bytes:
				self.processed_bytes += message.bytes
			self.view.refresh_progress_window()
