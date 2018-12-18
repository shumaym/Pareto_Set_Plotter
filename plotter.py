#!/usr/bin/env python3
import os
import glob
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from distutils.spawn import find_executable
import signal
import re
import subprocess
import sys
import getopt
import tempfile

version = '1.1'


def exit_gracefully(signum, frame):
	"""
	More elegant handling of keyboard interrupts.
	Enter 'Ctrl+C', then 'y' to terminate early.
	"""
	signal.signal(signal.SIGINT, original_sigint)
	try:
		input_text = input('\n\nReally Quit? (y/n)> ').lower().lstrip()
		if input_text != '' and input_text[0] == 'y':
			print('Exiting.')
			quit()
	except KeyboardInterrupt:
		print('\nExiting.')
		quit()
	signal.signal(signal.SIGINT, exit_gracefully)


original_sigint = signal.getsignal(signal.SIGINT)
signal.signal(signal.SIGINT, exit_gracefully)


def main():
	### Meta-parameters ###
	# Create lines between the starting node and the bar of the first dimension.
	show_sol_nestnode_lines = True
	# Show the resulting hypervolume of each generation in the GIFs/MP4s.
	# These must be included with the same filenames for each generation, with extension '.hv'.
	flag_show_hypervolumes = False
	# The file's generation number must be divisible by the file_stepping to be included.
	# If file_stepping == 1, every file is included.
	file_stepping = 1
	# Total duration of the GIF and MP4 in seconds.
	# Not accurate for GIFs, as the size of the GIF frames greatly impacts the frame rate.
	total_duration = 5

	### Image parameters ###
	background_colour = (0, 0, 0)
	width = 1000
	height = 374
	vert_margin = 0.10
	left_margin = 0.05
	right_margin = 0.075

	### Dimension bar parameters ###
	# Show the vertical bars representing spatial dimensions.
	flag_show_bars = True
	# Distance between the first bar and the left border.
	left_bar_margin = 0.10
	bar_width = 3
	bar_colour = (150, 150, 150)

	### Solution parameters ###
	sol_line_width = 2
	colour_best = (40, 135, 95)
	colour_worst = (40, 62, 130)
	
	### Scale parameters ###
	flag_show_scale = True
	# Number of numbered ticks along the scale
	scale_granularity = 5

	### Text parameters ###
	text_size = int(height * vert_margin / 1.7)
	text_font = ImageFont.truetype('/home/m/ACO/Plotter/fonts/Roboto/Roboto-Regular.ttf', size=text_size)
	scale_text_size = int(right_margin * width / 5)
	scale_font = ImageFont.truetype('/home/m/ACO/Plotter/fonts/Roboto/Roboto-Regular.ttf', size=scale_text_size)
	top_text_position = (0.25 * text_size, 0.10 * text_size)
	bottom_text_position = (0.25 * text_size, height - 1.20 * text_size)
	text_colour = (255, 255, 255)

	### Read all command-line parameters ###
	try:
		opts, args = getopt.getopt(sys.argv[1:], 'hd:s:v', ['stepping=', 'duration=', 'help', 'version'])
		for opt, arg in opts:
			if opt == '--help':
				print('Options:')
				print(' -d N, --duration=N    the duration in seconds of the output media (default: 5)')
				print(' -s N, --stepping=N    only process a filename if its generation number is divisible by N')
				print(' -h                    try to include hypervolume data for each generation, if available')
				print(' --help                display this help page and exit')
				print(' -v, --version         display version information and exit')
				print('\n')
				quit()

			if opt == '-h':
				print('Will show hypervolumes for each run, if provided.')
				flag_show_hypervolumes = True

			elif opt in ('-d', '--duration'):
				try:
					arg = float(arg)
					if arg > 0:
						total_duration = float(arg)
						print('Media duration set to {0} seconds.'.format(total_duration))
					else:
						print('Provided duration is not valid. Setting to default of {0}'.format(total_duration))
				except ValueError:
					print('Provided duration is not valid. Setting to default of {0}'.format(total_duration))
			
			elif opt in ('-s', '--stepping'):
				try:
					arg = int(arg)
					if arg >= 1:
						file_stepping = int(arg)
						print('File stepping set to {0}.'.format(file_stepping))
					else:
						print('Provided stepping value is not valid. Setting to default of {0}.'.format(file_stepping))
				except ValueError:
					print('Provided stepping value is not valid. Setting to default of {0}.'.format(file_stepping))

			elif opt in ('-v', '--version'):
				print('plotter version {0}'.format(version))
				print('License LGPLv3: GNU LGPL version 3 <https://www.gnu.org/licenses/lgpl>.')
				print('Written by Mykel Shumay.')
				print('\n')
				quit()

	except getopt.GetoptError:
		print('\nError: Unrecognized option provided,'
			+ ' or an option that requires an argument was given none.')
		print('Call with option \'--help\' for the help page.\n\n')
		quit()

	### Find all .pos files in the current directory and section them into their Run numbers. ###
	files = sorted(glob.glob('*[Rr][Uu][Nn]*_gen*.pos'))
	if len(files) == 0:
		print('\nNo .pos files with generation numbers found. Exiting.')
		quit()

	run_nums = [int(x.lower().split('run')[1].split('_')[0]) for x in files]
	min_run_num = min(run_nums)
	max_run_num = max(run_nums)

	runs_files = []
	for run_num in range(min_run_num, max_run_num + 1):
		run_num_matches = [file for idx,file in enumerate(files) if int(run_nums[idx]) == run_num]
		if len(run_num_matches) > 0:
			runs_files.append((run_num, run_num_matches))

	### Create the output folders, if they don't yet exist. ###
	media_output_dir = './media/'
	try:
		os.makedirs(media_output_dir)
	except PermissionError:
		print('You do not have the adequate permissions to create the required folders. Exiting.')
		quit()
	except FileExistsError:
		pass

	gif_output_dir = media_output_dir + 'gifs/'
	try:
		os.makedirs(gif_output_dir)
	except PermissionError:
		print('You do not have the adequate permissions to create the required folders. Exiting.')
		quit()
	except FileExistsError:
		pass

	mp4_output_dir = media_output_dir + 'mp4s/'
	try:
		os.makedirs(mp4_output_dir)
	except PermissionError:
		print('You do not have the adequate permissions to create the required folders. Exiting.')
		quit()
	except FileExistsError:
		pass

	###
	# Check if 'convert' and 'ffmpeg' are installed, which may be used for post-processing.
	# Note: find_executable may return a non-executable if it's listed on the PATH.
	###
	if find_executable('convert') is not None:
		print('ImageMagick\'s convert was found;'
			+ ' will optimize the resulting GIFs.')
		flag_convert_exec = True
	else:
		flag_convert_exec = False

	if find_executable('ffmpeg') is not None:
		print('ffmpeg was found;'
			+ ' will create MP4s.')
		flag_ffmpeg_exec = True
	else:
		print('ffmpeg was _NOT_ found;'
			+ ' will _NOT_ create MP4s.')
		flag_ffmpeg_exec = False
	
	if flag_ffmpeg_exec and not flag_convert_exec:
		print('ffmpeg will be used to create moderately-optimized GIFs.')

	if not flag_ffmpeg_exec and not flag_convert_exec:
		print('\nWARNING: Unable to optimize GIFs. Please install imagemagick or ffmpeg.')
	if not flag_ffmpeg_exec:
		print('\nWARNING: Unable to create MP4s. Please install ffmpeg.')

	###
	# For each run, generate all frames.
	# Then, create a GIF (and possibly MP4) for generated frames.
	###
	for run_num,run in runs_files:
		images = []
		comments = []
		flag_run_show_hypervolumes = flag_show_hypervolumes
		flag_comments_read = False
		# Colour is determined by the provided solution rank if provided, otherwise by placement in file.
		flag_colour_by_rank = True
		
		print()
		for file in run[::file_stepping]:
			if flag_run_show_hypervolumes:
				hv = None
				try:
					hv_filename = ''.join([file[:-4], '.hv'])
					with open(hv_filename, 'r') as f:
						hv = float(f.read())
					if hv == '':
						print('File \'{0}\' is empty;'.format(file[:-4] + '.hv')
							+ ' will not attempt to show any hypervolumes this run.')
						flag_run_show_hypervolumes = False
				except FileNotFoundError:
					print('File \'{0}\' not found;'.format(file[:-4] + '.hv')
						+ ' will not attempt to show any hypervolumes this run.')
					flag_run_show_hypervolumes = False
				except ValueError:
					print('File \'{0}\' contains an invalid hypervolume value;'.format(file[:-4] + '.hv')
						+ ' will not attempt to show any hypervolumes this run.')
					flag_run_show_hypervolumes = False
				except PermissionError:
					print('You do not have the permissions to read file \'{0}\';'.format(file[:-4] + '.hv')
						+ ' will not attempt to show any hypervolumes for this run.')
					flag_run_show_hypervolumes = False

			try:
				with open(file, 'r') as f:
					lines = [line.rstrip('\n') for line in f]
			except FileNotFoundError:
				print('Unable to find file \'{0}\'; it may have been deleted.\nExiting.'.format(file))
				quit()
			except PermissionError:
				print('You do not have the permissions to read file \'{0}\'\nExiting.'.format(file))
				quit()

			sols = []
			for line in lines:
				if line[0] != '#':
					sols.append([float(x) for x in line.split('\t')])
				elif not flag_comments_read:
					comments.append(line)

			if not flag_comments_read:
				# Gather metadata from the first .pos file per Run.
				try:
					lang = [s for s in comments if '# Lang=' in s]
					if len(lang) > 0:
						lang = lang[0].split('=')[1]
					obj_function = [s for s in comments if '# Function=' in s][0].split('=')[1]
					scalarizing = [s for s in comments if '# Scalarizer=' in s][0].split('=')[1]
					k = int([s for s in comments if '# k=' in s][0].split('=')[1])
					n = int([s for s in comments if '# n=' in s][0].split('=')[1])
					Rmin = float([s for s in comments if '# Rmin=' in s][0].split('=')[1])
					Rmax = float([s for s in comments if '# Rmax=' in s][0].split('=')[1])
					
					dimensions = int(n)
					flag_comments_read = True
				except (IndexError, ValueError):
					print('Comments are not properly included in file \'{0}\'\nExiting.'.format(file))
					quit()

			if flag_colour_by_rank and len(sols[0]) < n + 1:
				print('Ranks were not included as an additional column in the \'.pos\' files of Run{0}.\n'.format(run_num)
					+ ' Solution colours will instead be determined by their position in the \'.pos\' files.')
				flag_colour_by_rank = False

			if flag_colour_by_rank:
				sols = sorted(sols, key=lambda x: x[-1])
				ranks = [int(sol[-1]) for sol in sols]
				ranks_max = max(ranks)

			im = Image.new('RGB', (width, height), background_colour)
			draw = ImageDraw.Draw(im) 

			### Modular construction of top row of text ###
			regex = re.compile('_gen{1}[0-9]+', re.IGNORECASE)
			gen = re.findall(regex, file)[0][4:]
			text_top_row = 'Gen: {0}'.format(gen)
			if flag_colour_by_rank:
				text_top_row += '{0:4}Ranks: {1:>3}'.format('', str(ranks_max))
			if flag_run_show_hypervolumes:
				num_spaces = 8 - len(str(ranks_max))
				text_top_row += '{0}HV: {1:.6e}'.format(' ' * num_spaces, float(hv))
			draw.text(top_text_position, text_top_row, fill=text_colour, font=text_font)

			### Modular construction of bottom row of text ###
			text_bottom_row = '{0}    k:{1}    n:{2}    {3}'.format(obj_function, str(k), str(n), scalarizing)
			if len(lang) > 0:
				text_bottom_row += '    {0}'.format(lang)
			draw.text(bottom_text_position, text_bottom_row, fill=text_colour, font=text_font)

			### Determine x-points of the vertical bars ###
			bar_locations = []
			for i in range(dimensions):
				bar_locations.append(left_bar_margin * width + i * 
					((1 - right_margin) * (width * (1 - left_bar_margin)))/(dimensions-1))

			### Determine the available solution colours ###
			num_colours = ranks_max if flag_colour_by_rank else len(sols)
			colours = np.expand_dims(
				np.array(np.linspace(colour_best[0], colour_worst[0], num_colours), dtype=np.int32),
				axis=1)
			colours = np.concatenate(
				(
					colours,
					np.expand_dims(
						np.array(np.linspace(colour_best[1], colour_worst[1], num_colours), dtype=np.int32),
					axis=1)
				),
				axis=1)
			colours = np.concatenate(
				(
					colours,
					np.expand_dims(
						np.array(np.linspace(colour_best[2], colour_worst[2], num_colours), dtype=np.int32),
					axis=1)
				),
				axis=1)

			###
			# Draw all solutions.
			# Order of sols is reversed so that the best solutions are drawn last.
			###
			for index, sol in reversed(list(enumerate(sols))):
				if flag_colour_by_rank:
					colour = (colours[ranks[index]-1,0], colours[ranks[index]-1,1], colours[ranks[index]-1,2])
				else:
					colour = (colours[index,0], colours[index,1], colours[index,2])

				starting_x = bar_locations[0]

				starting_y = (1 - (sol[0] - Rmin) / (Rmax - Rmin))
				starting_y *= height * (1 - 2 * vert_margin)
				starting_y += height * vert_margin
				starting_y = int(starting_y)

				# If set, create lines between the starting node and the bar of the first dimension.
				if show_sol_nestnode_lines:
					draw.line(
						(left_margin * width, height/2,
						starting_x, starting_y),
						fill=colour,
						width=sol_line_width)
				
				current_location = (starting_x, starting_y)
				
				# Draw a line for each dimension of the current sol.
				for i in range(1, dimensions):
					target_x = bar_locations[i]

					target_y = (1 - (sol[i] - Rmin) / (Rmax - Rmin))
					target_y *= height * (1 - 2 * vert_margin)
					target_y += height * vert_margin
					target_y = int(target_y)

					draw.line(
						(current_location[0], current_location[1],
						target_x, target_y),
						fill=colour,
						width=sol_line_width)
					current_location = (target_x, target_y)

			if flag_show_bars:
				for i in range(dimensions):
					x_point = bar_locations[i]
					draw.line(
						(x_point, height * vert_margin,
						x_point, height * (1. - vert_margin)),
						fill=bar_colour,
						width=bar_width)

			###
			# Draw a scale next to the right-most vertical bar.
			###
			if flag_show_scale:
				ticks = scale_granularity
				tick_length = 0.075 * right_margin * width
				tick_separation = (height * (1 - 2 * vert_margin)) / (ticks - 1)
				bar_length = height * (1 - 2 * vert_margin)

				for tick in range(ticks):
					x_point = bar_locations[dimensions-1]
					y_point = height * vert_margin + height * (1 - 2 * vert_margin) - tick * tick_separation
					draw.line((x_point, y_point, x_point + tick_length, y_point), fill=bar_colour, width=2)
					
					# Percentage of position along the bar, from the bottom
					scale_num = 1 - ((bar_length - tick * tick_separation) / bar_length)
					# Scale into the proper range
					scale_num *= Rmax - Rmin
					# Compensate for minimum offset
					scale_num += Rmin
					if abs(Rmax) >= 1000 or abs(Rmin) >= 1000:
						scale_text = '{0:.1e}'.format(scale_num)
					else:
						scale_text = '{0:.2f}'.format(scale_num)

					draw.text(
						(
							x_point + 1.5 * tick_length,
							y_point - 0.56 * scale_text_size
						),
						scale_text,
						fill=text_colour,
						font=scale_font)

			images.append(im)

		regex = re.compile('_gen{1}[0-9]+', re.IGNORECASE)
		output_filename = re.sub(regex, '', run[0])[:-4]
		frame_delay = 100 * total_duration / len(images)

		# Creation of the run's GIF file
		print('Creating {0}'.format(gif_output_dir + output_filename + '.gif'))
		if flag_convert_exec:
			IM_convert_gif(images, frame_delay, gif_output_dir, output_filename)
		elif flag_ffmpeg_exec:
			ffmpeg_gif(images, frame_delay, gif_output_dir, output_filename)
		else:
			pil_gif(images, frame_delay, gif_output_dir, output_filename)

		# Creation of the run's MP4 file
		if flag_ffmpeg_exec:
			print('Creating {0}'.format(mp4_output_dir + output_filename + '.mp4'))
			ffmpeg_mp4_h264(images, frame_delay, mp4_output_dir, output_filename)


def pil_gif(images, frame_delay, output_directory, output_filename):
	""" Uses PIL to create and save an unoptimized GIF. """
	images[0].save(
		output_directory + output_filename + '.gif',
		save_all=True,
		append_images=images[1:],
		duration=max(1.5, frame_delay),
		loop=0)


def IM_convert_gif(images, frame_delay, output_directory, output_filename):
	"""
	Uses ImageMagick's convert to create and save an optimized GIF.
	convert creates slightly smaller files than ffmpeg.
	Optimization flags may produce smaller files still,
	but the additional cost usually outweighs any benefits.
	"""
	gif_tempfile = tempfile.NamedTemporaryFile()
	images[0].save(gif_tempfile,
		format='GIF',
		save_all=True,
		append_images=images[1:],
		loop=0)
	gif_tempfile.seek(0)

	# If frame_delay is <= 1.5, the GIFs may play much slower than expected.
	frame_delay = max(1.5, frame_delay)

	convert_cmd = [
		'convert',
		'-delay', str(frame_delay),
		'-loop', '0',
		'-',
		# '-coalesce',
		# '-layers', 'Optimize',
		output_directory + output_filename + '.gif'
	]

	subprocess.run(convert_cmd, stdin=gif_tempfile)


def ffmpeg_gif(images, frame_delay, output_directory, output_filename):
	""" Uses ffmpeg to create and save an moderately-optimized GIF. """
	ffmpeg_cmd = [
		'ffmpeg',
		'-loglevel', 'quiet',
		'-framerate', str(100/frame_delay),
		'-f', 'image2pipe',
		'-vcodec', 'png',
		'-i', '-',			# Pipe input 
		'-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',
		'-pix_fmt', 'rgb8',
		'-r', '30',			# Playback FPS, improves VLC player playback
		'-y',				# Overwrite existing files
		output_directory + output_filename + '.gif']
	
	pipe = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
	for im in images:
		im.save(pipe.stdin, 'PNG')
	pipe.stdin.close()
	pipe.wait()

	if pipe.returncode != 0:
		raise subprocess.CalledProcessError(pipe.returncode, ffmpeg_cmd)


def ffmpeg_mp4_h264(images, frame_delay, output_directory, output_filename):
	"""
	Uses ffmpeg to create and save a moderately-optimized MP4 in H.264 encoding.
	The colour space is changed from RGB to YUV for efficiency,
	so the colours will look slightly off.
	"""
	ffmpeg_cmd = [
		'ffmpeg',
		'-loglevel', 'quiet',
		'-framerate', str(100/frame_delay),
		'-f', 'image2pipe',
		'-vcodec', 'png',
		'-i', '-',			# Pipe input 
		'-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',
		'-vcodec', 'libx264',
		# '-vcodec', 'libx264rgb',
		'-crf', '25',		# Constant quality [0-51], lower numbers -> higher quality
		'-maxrate', '10M',	# Target max bitrate/second
		'-bufsize', '5M',	# How often ffmpeg checks the actual bitrate against the target
		'-pix_fmt', 'yuv444p',
		# '-pix_fmt', 'yuv420p',
		# '-pix_fmt', 'yuv420p10le',
		# '-pix_fmt', 'gbrp',
		'-r', '30',			# Playback FPS, improves VLC player playback
		'-y',				# Overwrite existing files
		output_directory + output_filename + '.mp4']

	pipe = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
	for im in images:
		im.save(pipe.stdin, 'PNG')
	pipe.stdin.close()
	pipe.wait()

	if pipe.returncode != 0:
		raise subprocess.CalledProcessError(pipe.returncode, ffmpeg_cmd)


if __name__ == '__main__':
	main()