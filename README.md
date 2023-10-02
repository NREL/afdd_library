## Installation

Create a new conda environment with **python 3.9** or above (only need to do this once):
```
$ conda create -y -n afdd_library python=3.9 pip
$ conda activate afdd_library
```

Make sure you are using the latest version of `pip`:
```
$ pip install --upgrade pip
```

Install the libraries needed for this repository:
```
$ pip install -e .[dev]
```
