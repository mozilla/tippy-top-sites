import json
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


def _fetch_alexa_top_sites():
    r = requests.get(ALEXA_DATA_URL)
    z = zipfile.ZipFile(StringIO(r.content))
    rows = StringIO(z.read('top-1m.csv'))
    for row in rows:
        rank, domain = row.split(',')
        yield (int(rank), domain.strip())


def alexa_top_sites(count=1000):
    top = _fetch_alexa_top_sites()
    return [top.next() for x in xrange(count)]


def fetch_icons(url, user_agent=IPHONE_UA):
    icons = []
    browser = RoboBrowser(user_agent=user_agent)
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


def get_best_image(images):
    image_url = None
    image_width = 0
    for image in images:
        url = fix_url(image['href'])
        try:
            response = requests.get(url, headers={'User-agent': FIREFOX_UA})
            with Image.open(StringIO(response.content)) as img:
                width, height = img.size
                if width > image_width:
                    image_url = url
                    image_width = width
        except:
            pass

    if image_width < 90:
        # We don't want any images under 90px
        image_url = None

    return image_url


@click.command()
def make_manifest():
    results = []
    for _, hostname in alexa_top_sites(1000):
        url = 'https://{hostname}'.format(hostname=hostname)
        icons = fetch_icons(url)
        if len(icons) == 0:
            url = 'http://{hostname}'.format(hostname=hostname)
            icons = fetch_icons(url)
        if len(icons) == 0:
            continue
        icon = get_best_image(icons)
        if icon is None:
            continue
        results.append({
            'image_url': icon,
            'title': hostname.split('.')[0],
            'url': url
        })
    print json.dumps(results, indent=4)


if __name__ == '__main__':
    make_manifest()
