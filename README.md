# tippy-top-playground
Experimental stuff related to tippy top services

## make_manifest.py
To run the manifest generator script. In a new virtualenv:

```
$ pip install -r requirements.txt
$ python make_manifest.py --help
Usage: make_manifest.py [OPTIONS]

Options:
  --count INTEGER         Number of sites from Alexa Top Sites
  --saverawsitedata TEXT  Save the full data to the filename specified
  --help                  Show this message and exit.

$ python make_manifest.py --count 100 > icons.json
```
