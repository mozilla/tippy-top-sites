# tippy-top-sites
Scripts and tools related to tippy top services 

## make_manifest.py
To run the manifest generator script (note this script only supports Python3). In a new virtualenv:

```
$ pip install -r requirements.txt
$ python make_manifest.py --help
Usage: make_manifest.py [OPTIONS]

Options:
  --count INTEGER         Number of sites from a list of Top Sites that should
                          be used to generate the manifest. Default is 10.
  --topsitesfile PATH     A csv file containing comma separated rank and
                          domain information (in the same order) of the Top
                          Sites. If no file is provided then Alexa Top Sites
                          are used.
  --minwidth INTEGER      Minimum width of the site icon. Only those sites
                          that satisfy this requirement are added to the
                          manifest. Default is 96.
  --loadrawsitedata TEXT  Load the full data from the filename specified
  --saverawsitedata TEXT  Save the full data to the filename specified
  --help                  Show this message and exit.

$ python make_manifest.py --count 100 > icons.json
```
