# tippy-top-sites
Scripts and tools related to tippy top services 

## make_manifest.py
To run the manifest generator script (note this script only supports Python3). In a new virtualenv:

```
$ pip install -r requirements.txt
$ python make_manifest.py --help
Usage: make_manifest.py [OPTIONS]

Options:
  --count INTEGER         Number of sites from Alexa Top Sites
  --loadrawsitedata TEXT  Load the full data from the filename specified
  --saverawsitedata TEXT  Save the full data to the filename specified
  --help                  Show this message and exit.

$ python make_manifest.py --count 100 > icons.json
```
