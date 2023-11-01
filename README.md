## Installation

1. Clone the repo using git:
```
$ git clone https://github.com/NREL/afdd_library.git --branch demo
```
2. Install conda for virtual environment management. Create and activate a new virtual environment.
```
$ conda create -y -n afdd_library python=3.10.0
$ conda activate afdd_library
```

3. Make sure you are using the latest version of `pip`:
```
$ pip install --upgrade pip
```

4. Install the dependencies using pip\
To set up your environment to run the code, first install all requirements:
```
$ cd afdd_library
$ pip install -r requirements.txt
```

## Run Demo

Run the following command to start demo.
```
$ python main.py
```

## Point Mapping

After start the `main.py`, the `tag_report.txt` file created in the directory\
If the point mapping is incorrect, you can update the mapping information through the corresponding file.
```
1. PointMapping/taglookupdate.py
2. PointMapping/point.yaml
```
