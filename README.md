# Pareto Set Plotter

Using generational snapshots, this script creates visual representations of the progression of Pareto optimal sets created by many-objective ant colony optimizers.

Dependencies
-----
*	<b>Python3.5+</b>
*	<b>PIL</b> (Python Imaging Library)
*	<b>ffmpeg</b>: Used to create the GIFs and MP4s. The MP4 versions usually have substantially smaller filesizes and play at the intended frame rate.

Usage
-----
Run this script from within a folder containing generational ```.pos``` files, possibly created from my <a href="https://github.com/shumaym/iMOACOR-PyTorch">iMOACO<sub><b>R</b></sub> Implementation</a>; note that you must pass the option ```--snapshots``` to ```iMOACOR.py``` to create the generational ```.pos``` snapshots, which will be written to the ```snapshots``` directory.

Run with the following command:
```
python3 <path to plotter.py> [OPTIONS]
```

Options:
*	```-d N | --duration=N```: The duration in seconds of the output media (default: 5.0)
*	```-s N | --stepping=N```: Only process a filename if its generation number is divisible by N
*	```-h```: Attempt to include hypervolume data for each generation, if available
*	```--help```: Display the help page

For generational hypervolumes to be displayed, they must first be created in the same folder by the use of my <a href="https://github.com/shumaym/Hypervolume_Manager">Hypervolume Manager</a>. Make sure to use the same or compatible ```stepping``` values for each script.

By default, the colour of each solution is determined by its relative rank; to support this, each Pareto set solution must include an additional entry containing the solution's rank.