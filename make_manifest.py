import json
import logging
import re
import zipfile
import csv
from io import BytesIO, StringIO
from urllib.parse import urljoin

import click
import requests
from PIL import Image
from robobrowser import RoboBrowser

from nsfw import is_nsfw


LINK_SELECTOR = 'link[rel=apple-touch-icon], link[rel=apple-touch-icon-precomposed], link[rel="icon shortcut"], link[rel="shortcut icon"], link[rel="icon"]'
META_SELECTOR = 'meta[name=apple-touch-icon]'
FIREFOX_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:58.0) Gecko/20100101 Firefox/58.0'
IPHONE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 10_2_1 like Mac OS X) AppleWebKit/602.4.6 (KHTML, like Gecko) Version/10.0 Mobile/14D27 Safari/602.1'
ALEXA_DATA_URL = 'http://s3.amazonaws.com/alexa-static/top-1m.csv.zip'
# Domains we want to exclude
DOMAIN_BLACKLIST = [
    "higheurest.com",
    "blogspot.co.id",
    "pipeschannels.com",
    "blogspot.mx",
    "bestadbid.com",
    "googlevideo.com",
    "tqeobp89axcn.com",
    "ioredi.com",
    "moradu.com",
    "fedsit.com",
    "vebadu.com"
]
# Additional domains we want to include
DOMAIN_WHITELIST = [
    "mail.google.com",
    "go.twitch.tv"
]

logging.basicConfig(filename='debug.log',level=logging.INFO)


def _fetch_alexa_top_sites():
    r = requests.get(ALEXA_DATA_URL, timeout=60)
    z = zipfile.ZipFile(BytesIO(r.content))
    rows = StringIO(z.read('top-1m.csv').decode('UTF-8'))
    for row in rows:
        rank, domain = row.split(',')
        yield (int(rank), domain.strip())

def _fetch_top_sites(topsitesfile):
    with open(topsitesfile, newline='') as csvfile:
        rows = csv.reader(csvfile)
        for row in rows:
            if len(row) == 0:
                # skip empty lines
                continue
            yield (row[0], row[1])

def top_sites(topsitesfile, count):
    logging.info(f'Fetching top {count} sites')
    top_sites_generator = None
    if topsitesfile:
        top_sites_generator = _fetch_top_sites(topsitesfile)
    else:
        top_sites_generator = _fetch_alexa_top_sites()
    return [next(top_sites_generator) for x in range(count)]

def is_url_reachable(url):
    try:
        response = requests.get(url, headers={'User-agent': FIREFOX_UA}, timeout=60)
        return True if response.status_code == 200 else False
    except Exception as e:
        logging.info(f'Exception: "{str(e)}" while checking if "{url}" is reachable or not')
        return False

def fetch_icons(url, user_agent=IPHONE_UA):
    logging.info(f'Fetching icons for {url}')
    icons = []
    browser = RoboBrowser(user_agent=user_agent, parser='html.parser')
    try:
        browser.open(url, timeout=60)
        for link in browser.select(LINK_SELECTOR):
            icon = link.attrs
            icon_url = icon['href']
            if icon_url.startswith('data:'):
                continue
            if not icon_url.startswith('http') and not icon_url.startswith('//'):
                icon['href'] = urljoin(browser.url, icon_url)
            icons.append(icon)
        for meta in browser.select(META_SELECTOR):
            icon = meta.attrs
            icon_url = icon['content']
            if icon_url.startswith('data:'):
                continue
            if not icon_url.startswith('http') and not icon_url.startswith('//'):
                icon['href'] = urljoin(browser.url, icon_url)
            else:
                icon['href'] = icon_url
            icons.append(icon)
    except Exception as e:
        logging.info(f'Exception: "{str(e)}" while parsing icon urls from document')
        pass

    # Some domains keep favicon in the their root with file name "favicon.ico".
    # Add the icon url if this is the case.
    default_favicon_url = url+"/favicon.ico"
    if is_url_reachable(default_favicon_url):
        icons.append({"href":default_favicon_url})
    return icons

def fix_url(url):
    fixed = url
    if not url.startswith('http'):
        fixed = 'https:{url}'.format(url=url)
    return fixed


def get_best_icon(minwidth, images):
    image_url = None
    image_width = 0
    for image in images:
        url = fix_url(image.get('href'))
        width = None
        sizes = image.get('sizes')
        if sizes:
            try:
                width = int(sizes.split('x')[0])
            except:
                pass
        if width is None:
            try:
                response = requests.get(url, headers={'User-agent': FIREFOX_UA}, timeout=60)

                # Check if it's an SVG without a mask. Firefox doesn't support masked icons yet.
                if response.headers.get('Content-Type') == 'image/svg+xml' and 'mask' not in image:
                    # If it is. We want it. We are done here.
                    return url

                with Image.open(BytesIO(response.content)) as img:
                    width, _ = img.size
            except Exception as e:
                logging.info(f'Exception: "{str(e)}" fetching (or opening) icon {url}')
                pass
        if width and width > image_width:
            image_url = url
            image_width = width

    if image_width < minwidth:
        # We don't want any images under specified resolution
        image_url = None

    return image_url

def collect_icons_for_top_sites(minwidth, topsitesfile, count, extra_domains=None):
    results = []
    for rank, hostname in top_sites(topsitesfile, count) + [(-1, x) for x in extra_domains or []]:
        # Skip NSFW and blacklisted sites
        if is_nsfw(hostname) or hostname in DOMAIN_BLACKLIST:
            continue

        url = 'https://{hostname}'.format(hostname=hostname)
        icons = fetch_icons(url)
        if len(icons) == 0:
            # Retry with http
            url = 'http://{hostname}'.format(hostname=hostname)
            icons = fetch_icons(url)
        best_icon_url = get_best_icon(minwidth, icons)
        results.append({
            'hostname': hostname,
            'url': url,
            'icons': icons,
            'rank': rank,
            'best_icon': best_icon_url
        })
    logging.info('Done fetching icons')
    return results


@click.command()
@click.option('--count', default=10, help='Number of sites from a list of Top Sites that should be used to generate the manifest. Default is 10.')
@click.option('--topsitesfile', type=click.Path(exists=True), help='A csv file containing comma separated rank and domain information (in the same order) of the Top Sites. If no file is provided then Alexa Top Sites are used.')
@click.option('--minwidth', default=96, help='Minimum width of the site icon. Only those sites that satisfy this requirement are added to the manifest. Default is 96.')
@click.option('--loadrawsitedata', help='Load the full data from the filename specified')
@click.option('--saverawsitedata', help='Save the full data to the filename specified')
def make_manifest(count, minwidth, topsitesfile, saverawsitedata, loadrawsitedata):
    results = []

    if loadrawsitedata:
        logging.info(f'Loading raw icon data from {loadrawsitedata}')
        with open(loadrawsitedata) as infile:
            sites_with_icons = json.loads(infile.read())
    else:
        sites_with_icons = collect_icons_for_top_sites(minwidth, topsitesfile, count, extra_domains=DOMAIN_WHITELIST);
        if saverawsitedata:
            logging.info(f'Saving raw icon data to {saverawsitedata}')
            with open(saverawsitedata, 'w') as outfile:
                json.dump(sites_with_icons, outfile, indent=4)

    for site in sites_with_icons:
        hostname = site.get('hostname')
        url = site.get('url')
        icon = site.get('best_icon')
        if icon is None:
            continue
        existing = next((x for x in results if x.get('image_url') == icon), None)
        if existing:
            existing.get('domains').append(hostname)
        else:
            results.append({
                'image_url': icon,
                'domains': [hostname]
            })

    # Sort alphabetically
    results = sorted(results, key=lambda site: site['domains'][0])

    click.echo(json.dumps(results, indent=4))


if __name__ == '__main__':
    make_manifest()
