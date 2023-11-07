import sys
import os
import sqlite3
from optparse import OptionParser
from bs4 import BeautifulSoup, Tag
import requests

def dict_factory(cursor, row):
    return row[0]

def parse_url(url: str, conn: sqlite3.Connection, urls: list, root: str, verbose: bool = False, fork: int = 1) -> list:
    print(f'Parsing url:{url}...')
    if not isinstance(url, str):
        return urls
    
    response: requests.Response = None
    user_agent: dict = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'}
    try:
        response = requests.get(url, timeout=10, headers=user_agent, allow_redirects=False)
    except Exception as ex1:
        print(f'19:{ex1}')
        return urls
    
    if response is None:
        print('Invalid response!')
        return urls
    
    if response.status_code != 200:
        print(response.reason)
        return urls
    
    content_type: str = response.headers.get('Content-Type')
    if 'text/html' not in content_type.lower():
        print(f'Not html content:{content_type}')
        return urls

    bs: BeautifulSoup = None
    try:
        bs = BeautifulSoup(response.text, 'html.parser')
    except Exception as ex2:
        print(f'34:{ex2}')
        return urls
    
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
                link = f'{protocol}{www}.{hostname}.{domain}{link}'
            
            print(f'Found url:{link}')
            if link.lower().startswith('http://') or link.lower().startswith('https://'):
                if link not in urls:
                    urls.append(link)

                    if fork == 1:
                        if link.startswith(root):
                            accepted = True
                    elif fork == 2:
                        accepted = True
                
            if not accepted:
                print(f'Ignored url:{link}')
            else:
                conn.execute('INSERT INTO urls(url) VALUES(?)', (link,))
                conn.commit()
                print(f'Saved url:{link}')
                parse_url(link, conn, urls, root, verbose, fork)

    return urls


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

if __name__=="__main__":
    parser: OptionParser = OptionParser('%prog [OPTIONS] URL')
    parser.add_option('-v','--verbose', default=False, help='Print many as many runtime logs')
    parser.add_option('-f','--fork', default=1, help='Fork encountered links(0=No fork,1=Fork only links within the same domain, 2=Fork any encountered link)')
    parser.add_option('-o','--out', default='a.sqlite3', help='Output file and format. Format will be determined by file extension. Only sqlite3 and json formats are supported')

    (opts, args) = parser.parse_args()
    #Validate options
    verbose: bool = False
    if opts.verbose is not None:
        if str(opts.verbose).lower() == '1' or str(opts.verbose).lower()=='true':
            verbose = True
    fork: int = 1
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
    output: str = '<%URL%>.sqlite3'
    if opts.out is not None:
        output = str(opts.out)
    if (not output.endswith('.sql')) and (not output.endswith('.sqlite3')) and (not output.endswith('.json')):
        print('Invalid output file extension! Only .sql/.sqlite3/json can be specified.')
        exit(2)
        

    #Validate url
    if len(args) <= 0:
        print('No any url is specified!')
        exit(2)

    url: str = args[0]
    if (not url.startswith('http://')) and(not url.startswith('https://')):
        print('Invalid url:{url}! URL must be start with http:// or https://')
        exit(3)
    
    protocol, www, hostname, domain = url_extract(url)
    output = output.replace('<%URL%>',hostname)

    #Connect database
    conn: sqlite3.Connection = None
    try:
        conn = sqlite3.connect(output)
    except Exception as ex:
        print(ex)
        exit(4)
    
    cur = conn.cursor()
    table_exist: bool = False
    urls: list = []
    try:
        result = cur.execute('SELECT name FROM sqlite_master WHERE type="table"')
        for row in result.fetchall():
            if 'urls' in row:
                table_exist = True
                break
        if not table_exist:
            cur.execute('CREATE TABLE urls(id INTEGER PRIMARY KEY, url VARCHAR(255) NOT NULL)')
            cur.execute('INSERT INTO urls(url) VALUES(?)', ('https://www.oxfordlearnersdictionaries.com/wordlists/oxford3000-5000',))
            conn.commit()
        else:
            org_factory = conn.row_factory
            conn.row_factory = dict_factory
            result = conn.execute('SELECT url FROM urls')
            urls = result.fetchall()
            conn.row_factory = org_factory
    except Exception as ex:
        print(ex)
        exit(5)

    parse_url(url, conn, urls, f'{protocol}{www}.{hostname}.{domain}')

    conn.close()
