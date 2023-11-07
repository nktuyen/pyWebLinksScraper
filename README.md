# pyWebLinksScraper
Scap web links from specified url

# HOW TO
python3 wlsc.py [OPTIONS] URL
 - Example: python3 wlsc.py --verbose=true --fork=true --out=links.sql

## URL
 - Specified url to scrap. Only single url is accepted.

## OPTIONS
### -h/--help
- Print help

### -v/--verbose
- Print many as many runtime logs

### -f/--fork
- Fork encountered links.
- Accepted values:
  - 0: No fork.
  - 1: Fork only links within the same domain.
  - 2: Fork any encountered link.

### -o/--out
- Output file and format. Format will be determined by file extension. Only sqlite3 and json formats are supported. If not specified, default output file will be **a.sqlite3**
