import sys
import os
import sqlite3
from optparse import OptionParser
from bs4 import BeautifulSoup, Tag
import concurrent.futures
import gevent.monkey
from multiprocessing import Lock
gevent.monkey.patch_all()

import requests

def dict_factory(cursor, row):
    return row[0]

def parse_url(session: requests.Session, url: str, handle, urls: list, root: str, verbose: bool = False, fork: int = 1, locker: Lock = None,  redirects: bool = False):
    print(f'Parsing url:{url}...')
    if not isinstance(url, str):
        return
    
    response: requests.Response = None
    user_agent: dict = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'}
    try:
        response = session.get(url, timeout=10, headers=user_agent, allow_redirects=redirects)
    except Exception as ex1:
        print(f'25:{ex1}')
        response = None
        return
    
    if response is None:
        print('Invalid response!')
        return
    
    if response.status_code != 200:
        print(f'[34]{response.reason}')
        response.close()
        return
    
    content_type: str = response.headers.get('Content-Type')
    if 'text/html' not in content_type.lower():
        print(f'Not html content:{content_type}')
        response.close()
        return

    bs: BeautifulSoup = None
    try:
        bs = BeautifulSoup(response.text, 'html.parser')
    except Exception as ex2:
        print(f'[48]:{ex2}')
        response.close()
        return
    
    response.close()
    response = None
    link: str = ''
    accepted: bool = False
    anchor: Tag = None
    anchors: list = bs.find_all('a')
    for a in anchors:
        anchor = a
        accepted = False
        if anchor.has_attr('href'):
            link = anchor['href'].strip()
            if link.startswith('/') or link.startswith('#') or link.startswith('?'):
                protocol, www, hostname, domain = url_extract(url)
                if len(www) > 0:
                    link = f'{protocol}{www}.{hostname}.{domain}{link}'
                else:
                    link = f'{protocol}{hostname}.{domain}{link}'
            
            print(f'Found url:{link}')
            if link.lower().startswith('http://') or link.lower().startswith('https://'):
                if link not in urls:
                    urls.append(link)

                    if fork == 1:
                        #print(f'root:{root}, link={link}')
                        if link.startswith(root):
                            accepted = True
                    elif fork == 2:
                        accepted = True
                
            if not accepted:
                print(f'Ignored url:{link}')
            else:
                with locker:
                    if isinstance(handle, sqlite3.Connection):
                        handle.execute('INSERT INTO urls(url) VALUES(?)', (link,))
                        handle.commit()
                    else:
                        handle.seek(0,2)
                        handle.write(f'{link}\n')
                        handle.flush()
                    print(f'Saved url:{link}')
                parse_url(session, link, handle, urls, root, verbose, fork, locker, redirects)


def url_extract(url: str):
    """
    Extract hostname and domain-name from specified url
    """
    if not isinstance(url, str):
        return ('', '', '', '')

    protocol: str = ''
    if url.lower().startswith('http://'):
        protocol = 'http://'
    elif url.lower().startswith('https://'):
        protocol = 'https://'
    else:
        return ('', '', '', '')
    
    start: int = len(protocol)
    domain: str = url[start:]
    end: int = domain.find('/')
    if end == -1:
        end1: int = domain.find('#')
        if end1 == -1:
            end1 = len(domain)
        end2: int = domain.find('?')
        if end2 == -1:
            end2 = len(domain)
        end = min(end1, end2)
    if end == -1:
        end = len(domain)
    domain = domain[:end]
    www: str = ''
    host: str = ''
    if domain.lower().startswith('www.'):
        www = 'www'
        domain = domain[len(www) + 1:]
    start = domain.find('.')
    if start != -1:
        host = domain[:start]
        domain = domain[start+1:]
    return (protocol, www, host, domain)


def url_get_root(url: str) -> str:
    protocol,www,host,domain = url_extract(url)
    if len(www) > 0:
        return f'{protocol}{www}.{host}.{domain}'
    else:
        return f'{protocol}{host}.{domain}'

if __name__=="__main__":
    parser: OptionParser = OptionParser('%prog [OPTIONS] URL')
    parser.add_option('-v','--verbose', action="store_false", help='Print many as many runtime logs')
    parser.add_option('-f','--fork', default=1, help='Fork encountered links(0=No fork,1=Fork only links within the same domain, 2=Fork any encountered link)')
    parser.add_option('-o','--out', default=None, help='Output file and format. Format will be determined by file extension. Only sqlite3 and json formats are supported. If not specified, output file will be [DOMAIN NAME].txt')
    parser.add_option('-r', '--allow-redirect', action="store_false", help='Whether or not allow http redirect')
    

    (opts, args) = parser.parse_args()
    #Validate options
    verbose: bool = False
    if opts.verbose is not None:
        verbose = True
    fork: int = 1
    redirect: bool = False
    if opts.allow_redirect is not None:
        redirect = True
    if opts.fork is not None:
        if str(opts.fork)=='0':
            fork = 0
        elif str(opts.fork) == '1':
            fork = 1
        elif str(opts.fork) == '2':
            fork = 2
        else:
            print(f'Invalid fork option:{opts.fork}!')
            exit(1)
    output: str = None
    if opts.out is not None:
        output = str(opts.out)
        if (not output.lower().endswith('.sqlite3')) and (not output.lower().endswith('.txt')):
            print('Invalid output file extension! Only .sqlite3/.txt can be specified.')
            exit(2)
    #Validate url
    if len(args) <= 0:
        print('No any url is specified!')
        exit(2)

    input_urls: list = []
    for url in args:
        if (not url.startswith('http://')) and(not url.startswith('https://')):
            print(f'Invalid url:{url}! URL must be start with http:// or https://')
            exit(3)
        input_urls.append(url)
    
    if output is None:
        if len(input_urls) == 1:
            _,_,host_name, domain_name =  url_extract(input_urls[0])
            output = f'urls{os.sep}{host_name}.{domain_name}.txt'
            if not os.path.exists('urls'):
                try:
                    os.mkdir('urls')
                except:
                    pass
        else:
            output = 'a.sqlite3'

    handle = None
    urls: list = []
    #Connect database
    try:
        if output.lower().endswith('.sqlite3'):
            handle = sqlite3.connect(output)
            cur = handle.cursor()
            table_exist: bool = False
            result = cur.execute('SELECT name FROM sqlite_master WHERE type=?',('table',))
            for row in result.fetchall():
                if 'urls' in row:
                    table_exist = True
                    break
            if not table_exist:
                cur.execute('CREATE TABLE urls(id INTEGER PRIMARY KEY, url VARCHAR(1024) NOT NULL UNIQUE, visits INTEGER DEFAULT 0)')
                #cur.execute('INSERT INTO urls(url) VALUES(?)', ('https://www.oxfordlearnersdictionaries.com/wordlists/oxford3000-5000',))
                handle.commit()
            else:
                org_factory = handle.row_factory
                handle.row_factory = dict_factory
                result = handle.execute('SELECT url FROM urls')
                urls = result.fetchall()
                handle.row_factory = org_factory
        else:
            if os.path.exists(output):
                handle = open(output, 'r')
                urls = handle.readlines()
                handle.close()
            handle = open(output, 'a+')
    except Exception as ex:
        print(f'[207]{ex}')
        exit(4)
    
    session: requests.Session = requests.Session()
    urls += input_urls
    locker = Lock()
    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as executor:
        future_to_urls = { executor.submit(parse_url, session, url, handle, urls, url_get_root(url), verbose, fork, locker, redirect) : url for url in input_urls}