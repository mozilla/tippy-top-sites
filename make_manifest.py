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


LINK_SELECTOR = 'link[rel=apple-touch-icon], link[rel=apple-touch-icon-precomposed], link[rel="icon shortcut"], link[rel="shortcut icon"], link[rel="icon"], link[rel="SHORTCUT ICON"], link[rel="fluid-icon"]'
META_SELECTOR = 'meta[name=apple-touch-icon]'
FIREFOX_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:58.0) Gecko/20100101 Firefox/58.0'
IPHONE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 10_2_1 like Mac OS X) AppleWebKit/602.4.6 (KHTML, like Gecko) Version/10.0 Mobile/14D27 Safari/602.1'
ALEXA_DATA_URL = 'http://s3.amazonaws.com/alexa-static/top-1m.csv.zip'
SVG_ICON_WIDTH = "SVG_ICON_WIDTH"
# Domains we want to exclude
DOMAIN_EXCLUSION_LIST = [
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

def extra_sites(extrafile):
    logging.info(f'Fetching extra sites')
    extra_sites_generator = None
    extra_sites_generator = _fetch_top_sites(extrafile)
    return list(extra_sites_generator)

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

    # If the document doesn't specify favicon via rel attribute of link tag then check
    # if "favicon.ico" file is present in the root of the domain as some domains keep
    # favicon in their root without specifying them in the document.
    # Add the icon url if this is the case.
    if len(icons) == 0:
        default_favicon_url = f"{url}/favicon.ico"
        if is_url_reachable(default_favicon_url):
            icons.append({"href": default_favicon_url})

    return icons

def fix_url(url):
    fixed = url
    if not url.startswith('http'):
        fixed = 'https:{url}'.format(url=url)
    return fixed


def get_best_icon(images):
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

                # If it is an SVG, then return this as the best icon because SVG images are scalable,
                # can be printed with high quality at any resolution and SVG graphics do NOT
                # lose any quality if they are zoomed or resized.
                if response.headers.get('Content-Type') == 'image/svg+xml':
                    # Firefox doesn't support masked icons yet.
                    if 'mask' not in image:
                        # If it is not then we want it. We are done here.
                        return (url, SVG_ICON_WIDTH)
                    else:
                        logging.info(f'SVG icon "{image}" is masked')
                        continue
                with Image.open(BytesIO(response.content)) as img:
                    width, height = img.size
                    if width != height:
                        logging.info(f'icon shape "{width}*{height}" is not square')
                        width = min(width, height)
            except Exception as e:
                logging.info(f'Exception: "{str(e)}" fetching (or opening) icon {url}')
                pass
        if width and width > image_width:
            image_url = url
            image_width = width

    return (image_url, image_width)

def collect_icons_for_top_sites(topsitesfile, extrafile, count):
    results = []
    extra_domains = []
    if extrafile:
        # Add extra domains if extra file is provided by user
        extra_domains = extra_sites(extrafile)

    for rank, hostname in top_sites(topsitesfile, count) + extra_domains:
        # Skip NSFW and blacklisted sites
        if is_nsfw(hostname) or hostname in DOMAIN_EXCLUSION_LIST:
            continue

        url = 'https://{hostname}'.format(hostname=hostname)
        icons = fetch_icons(url)
        if len(icons) == 0 and 'www.' not in hostname:
            # Retry with www. in the hostname as some domains require it explicitly.
            url = f"https://www.{hostname}"
            icons = fetch_icons(url)

        best_icon_url, best_icon_width = get_best_icon(icons)
        results.append({
            'hostname': hostname,
            'url': url,
            'icons': icons,
            'rank': rank,
            'best_icon_url': best_icon_url,
            'best_icon_width': best_icon_width
        })
    logging.info('Done fetching icons')
    return results


@click.command()
@click.option('--count', default=10, help='Number of sites from a list of Top Sites that should be used to generate the manifest. Default is 10.')
@click.option('--topsitesfile', type=click.Path(exists=True), help='A csv file containing comma separated rank and domain information (in the same order) of the Top Sites. If no file is provided then Alexa Top Sites are used.')
@click.option('--extrafile', type=click.Path(exists=True), help='A csv file containing domain information of extra top sites. If no file is provided then no extra Top Sites.')
@click.option('--minwidth', default=96, help='Minimum width of the site icon. Only those sites that satisfy this requirement are added to the manifest. Default is 96.')
@click.option('--loadrawsitedata', help='Load the full data from the filename specified')
@click.option('--saverawsitedata', help='Save the full data to the filename specified')
def make_manifest(count, minwidth, topsitesfile, extrafile, saverawsitedata, loadrawsitedata):
    results = []

    if loadrawsitedata:
        logging.info(f'Loading raw icon data from {loadrawsitedata}')
        with open(loadrawsitedata) as infile:
            sites_with_icons = json.loads(infile.read())
    else:
        sites_with_icons = collect_icons_for_top_sites(topsitesfile, extrafile, count)
        if saverawsitedata:
            logging.info(f'Saving raw icon data to {saverawsitedata}')
            with open(saverawsitedata, 'w') as outfile:
                json.dump(sites_with_icons, outfile, indent=4)

    for site in sites_with_icons:
        hostname = site.get('hostname')
        url = site.get('url')
        icon = site.get('best_icon_url')
        icon_width = site.get('best_icon_width')

        # check if there is a best icon that satisfies the minwidth criteria
        if (icon is None) or ((icon_width != SVG_ICON_WIDTH) and (icon_width < minwidth)):
            logging.info(f'No icon for "{url}" (best icon width: {icon_width})')
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
