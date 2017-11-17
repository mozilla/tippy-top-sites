import json
import logging
import re
import zipfile
from StringIO import StringIO
from urlparse import urlparse

import click
import requests
from PIL import Image
from robobrowser import RoboBrowser


ICON_SELECTOR = 'link[rel=apple-touch-icon], link[rel=apple-touch-icon-precomposed], link[rel="icon shortcut"], link[rel="shortcut icon"], link[rel="icon"]'
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
    r = requests.get(ALEXA_DATA_URL)
    z = zipfile.ZipFile(StringIO(r.content))
    rows = StringIO(z.read('top-1m.csv'))
    for row in rows:
        rank, domain = row.split(',')
        yield (int(rank), domain.strip())


def alexa_top_sites(count=1000):
    logging.info('Fetching Alexa top {count} sites'.format(count=count))
    top = _fetch_alexa_top_sites()
    return [top.next() for x in xrange(count)]


def fetch_icons(url, user_agent=IPHONE_UA):
    logging.info('Fetching icons for {url}'.format(url=url))
    icons = []
    browser = RoboBrowser(user_agent=user_agent, parser='html.parser')
    try:
        browser.open(url)
        for link in browser.select(ICON_SELECTOR):
            icon = link.attrs
            icon_url = icon['href']
            if not icon_url.startswith('http') and not icon_url.startswith('//'):
                parsed_url = urlparse(browser.url)
                icon['href'] = '{scheme}://{hostname}{path}'.format(scheme=parsed_url.scheme, hostname=parsed_url.netloc, path=icon_url)
            icons.append(icon)
    except:
        pass
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
                response = requests.get(url, headers={'User-agent': FIREFOX_UA})

                # Check if it's an SVG without a mask. Firefox doesn't support masked icons yet.
                if response.headers.get('Content-Type') == 'image/svg+xml' and not image.get('mask'):
                    # If it is. We want it. We are done here.
                    return image_url

                with Image.open(StringIO(response.content)) as img:
                    width, _ = img.size
            except:
                pass
        if width and width > image_width:
            image_url = url
            image_width = width

    if image_width < 96:
        # We don't want any images under 96px
        image_url = None

    return image_url


def collect_icons_for_alexa_top(count, extra_domains=None):
    results = []
    for rank, hostname in alexa_top_sites(count) + [(-1, x) for x in extra_domains or []]:
        url = 'https://{hostname}'.format(hostname=hostname)
        icons = fetch_icons(url)
        if len(icons) == 0:
            # Retry with http
            url = 'http://{hostname}'.format(hostname=hostname)
            icons = fetch_icons(url)
        results.append({
            'hostname': hostname,
            'url': url,
            'icons': icons,
            'rank': rank,
            'best_icon': get_best_icon(icons)
        })
    logging.info('Done fetching icons')
    return results


@click.command()
@click.option('--count', default=10, help='Number of sites from Alexa Top Sites')
@click.option('--loadrawsitedata', help='Load the full data from the filename specified')
@click.option('--saverawsitedata', help='Save the full data to the filename specified')
def make_manifest(count, saverawsitedata, loadrawsitedata):
    results = []

    if loadrawsitedata:
        logging.info('Loading raw icon data from {filename}'.format(filename=loadrawsitedata))
        with open(loadrawsitedata) as infile:
            sites_with_icons = json.loads(infile.read())
    else:
        sites_with_icons = collect_icons_for_alexa_top(count, extra_domains=DOMAIN_WHITELIST);
        if saverawsitedata:
            logging.info('Saving raw icon data to {filename}'.format(filename=saverawsitedata))
            with open(saverawsitedata, 'w') as outfile:
                json.dump(sites_with_icons, outfile, indent=4)

    for site in sites_with_icons[:count]:
        hostname = site.get('hostname')
        if hostname in DOMAIN_BLACKLIST:
            continue
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

    click.echo(json.dumps(results, indent=4))


if __name__ == '__main__':
    make_manifest()
