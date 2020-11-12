# removeheaders.py

# Very simple script that reads in a text file delimited by '<pb>' and writes
# it back out, sans running headers. All the cool stuff is done in the
# headers module. This is just a wrapper.

# Only thing to warn about: it assumes sourcefiles end with '.txt'

# USAGE:
#
# python removeheaders.py /path/to/infolder /path/to/outfolder

import os, sys, csv
import header
import SonicScrewdriver as utils
import tarfile

args = sys.argv

infolder = args[1]
outfolder = args[2]

metadict = dict()


with open('romannumerals.txt', encoding = 'utf-8') as f:
    romannumerals = [x.strip() for x in f.readlines()]

if not infolder.endswith('/'):
    infolder = infolder + '/'
if not outfolder.endswith('/'):
    outfolder = outfolder + '/'

infiles = [x for x in os.listdir(infolder) if x.endswith('.tar')]

alltheids = []

for afile in infiles:

    tar = tarfile.open(infolder + afile)
    namelist = tar.getnames()
    maxpage = 0

    for n in namelist:
        parts = n.split('/')
        if len(parts) > 1:
            pagenum = int(parts[1].replace('.txt', ''))
            if pagenum > maxpage:
                maxpage = pagenum

    prefix = parts[0]

    pages = []

    for i in range(0, maxpage + 1):
        filename = prefix + '/' + str(i) + '.txt'
        thispage = tar.extractfile(filename)
        page = [x.decode('utf-8') for x in thispage.readlines()]
        pages.append(page)

    pagelist, removed = header.remove_headers(pages, romannumerals)

    outpath = outfolder + afile
    outpath = outpath.replace('.tar', '.txt')
    with open(outpath, mode = 'w', encoding = 'utf-8') as f:
        for idx, page in enumerate(pagelist):
            f.write('\n<#PG# ' + str(idx) + '>\n')
            for line in page:
                f.write(line)

    theid = utils.dirty_pairtree(afile.replace('.tar', ''))
    alltheids.append(theid)

# with open(outfolder + 'nonfictionmetadata.csv', mode = 'w', encoding = 'utf-8') as f:
#     writer = csv.DictWriter(f, fieldnames = fieldnames)
#     writer.writeheader()
#     for anid in alltheids:
#         row = metadict[anid]
#         writer.writerow(row)









