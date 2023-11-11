# pyWebLinksScraper
Scap web links from specified web page

# HOW TO
python3 wlsc.py [OPTIONS] URL
 - Example: python3 wlsc.py --verbose=true --fork=true --out=links.sqlite3

## URL
 - Specified url to scrap. Only single url is accepted.

## OPTIONS
### -h/--help
- Print help

### -v/--verbose
- Print many as many runtime logs. Default is **False**

### -f/--fork
- Fork encountered links.
- Accepted values:
  - 0: No fork.
  - 1: Fork only links within the same domain.
  - 2: Fork any encountered link.
- Default value is **1**

### -o/--out
- Output file and format. Format will be determined by file extension. Currently, only sqlite3 and text files format is supported. If not specified, default output file will be **a.sqlite3**. If sqlite3 file is specified, found urls will be stored in a table named **urls**. If a text file is specified, found urls will be saved line by line to the file.
