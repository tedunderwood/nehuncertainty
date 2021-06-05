# measure_overlap

import os, re, argparse, sys, time
from difflib import SequenceMatcher
from collections import Counter

import pandas as pd

args = sys.argv

gutentarget = args[1]

gfiles = os.listdir('guten' + gutentarget + '/')

gutenids = [x.replace('.txt', '') for x in gfiles if x.endswith('.txt')]

print(len(gutenids))

hfiles = os.listdir('test/hathi/')

chunkdict = dict()

for h in hfiles:
    chunkid = h.replace('.txt', '')
    gid = h.split('_')[0]
    if gid not in chunkdict:
        chunkdict[gid] = []
    chunkdict[gid].append(chunkid)

def get_gbindex(filename):
    return filename.split('_')[0]

def matchpositions(gtext, htext, position, tristart, snippet):
    snippetlength = len(snippet)
    gstart = position - tristart
    gend = gstart + snippetlength

    if gstart < 0:
        gstart = 0
    if gend > len(gtext):
        gend = len(gtext)

    gsnip = gtext[gstart: gend]

    matcher = SequenceMatcher(None, snippet, gsnip)

    matched = False

    if matcher.real_quick_ratio() > .6:
        closeness = matcher.ratio()

        if closeness > .75:
            matched = True
    else:
        closeness = 0.6

    return matched, closeness

lexicon = set()

outfilename = 'hathinocorrerrs' + gutentarget + '.tsv'

alreadyhave = set()

if not os.path.isfile(outfilename):

    with open(outfilename, mode = 'w', encoding = 'utf-8') as f:
        f.write('chunkid\tpassagefails\tworderrors\n')

else:
    alreadydf = pd.read_csv(outfilename, sep = '\t')
    for idx, row in alreadydf.iterrows():
        alreadyhave.add(get_gbindex(row['chunkid']))

ctr = 0
with open('/Users/tunder/Dropbox/DataMunging/rulesets/MainDictionary.txt', encoding = 'utf-8') as f:
    for line in f:
        ctr += 1
        fields = line.split('\t')
        lexicon.add(fields[0])
        if ctr > 50000:
            break

for g in gutenids:
    if g not in chunkdict:
        print('error', g)
        continue
    if g in alreadyhave:
        print('already have: ', g)
        continue

    htids = chunkdict[g]

    with open('guten_set/' + g + '.txt', encoding = 'utf-8') as f:
        gtext = f.read().lower()

    gutenwords = set([x for x in re.split("\W+", gtext) if len(x) > 0])

    gtext = gtext.replace('-\n', '').replace('\n', ' ').replace('ſ', 's')

    index = dict()

    for idx in range(0, len(gtext) - 3):
        trigram = gtext[idx: idx + 3]
        if trigram not in index:
            index[trigram] = []
        index[trigram].append(idx)

    print(g, "indexed.")

    lastposition = 0

    rows = []

    for h in sorted(htids):     # it helps to go in order

        starttime = time.time()

        with open('test/hathi/' + h + '.txt', encoding = 'utf-8') as f:

            hlines = [x.lower() for x in f.readlines() if not x.startswith('<#PG#')]

        htext = ''.join(hlines)

        htext = htext.replace('-\n', ' ').replace('\n', ' ')

        matchedchars = 0
        unmatchedchars = 0
        continuations = 0

        lastmatched = True
        onebeforematched = True

        hwords = re.split(("\W+"), htext) # notice that because of the capturing parentheses
                                          # this also returns the delimiters
        hlen = len(hwords)
        hstart = 0

        totalmatchedwords = 0
        totalcorrectmatchedwords = 0

        for hstart in range(0, hlen, 10):

            hstop = hstart + 10

            if hstop > hlen:
                hstop = hlen

            snippet = ' '.join(hwords[hstart: hstop])

            snippet = snippet.replace('ſ', 's').replace('ﬁ', 'fi')

            snippetlen = len(snippet)

            matched, closeness = matchpositions(gtext, htext, lastposition, 0, snippet)

            if not matched and closeness > 0.7:
                lastposition += 2
                matched, closeness2 = matchpositions(gtext, htext, lastposition, 0, snippet)

                if not matched and closeness2 < closeness:
                    lastposition -= 5
                    matched, closeness3 = matchpositions(gtext, htext, lastposition, 0, snippet)
                else:
                    lastposition += 3
                    matched, closeness3 = matchpositions(gtext, htext, lastposition, 0, snippet)

            if not matched:

                if lastmatched:
                    trials = 5
                elif onebeforematched:
                    trials = 4
                else:
                    trials = 3

                trigramdict = dict()
                trigramset = set()

                for idx in range(0, snippetlen - 3, 3):
                    trigram = snippet[idx: idx + 3]
                    if trigram in index and trigram not in trigramset:
                        trigramdict[trigram] = idx
                        trigramset.add(trigram)

                trituples = []
                for trigram in trigramset:
                    tricount = index[trigram]
                    trituples.append((tricount, trigram))

                trituples.sort(reverse = True)

                if trials > len(trituples):
                    trials = len(trituples)

                for idx in range(trials):

                    trimatch = trituples[idx][1]

                    tristart = trigramdict[trimatch]

                    gmap = index[trimatch]

                    gmap_in_prob_order = sorted(gmap, key=lambda x: abs(lastposition - x))

                    for position in gmap:
                        matched, closeness = matchpositions(gtext, htext, position, tristart, snippet)

                        if matched:
                            break


                    if matched:
                        break
                    else:
                        position = lastposition

            else:
                position = lastposition
                continuations += 1

            if matched:
                matchedchars += snippetlen
                lastposition = position + snippetlen
                lastmatched = True
                onebeforematched = True
                for word in hwords[hstart: hstop]:
                    if len(word) > 0 and word[0].isalpha():
                        totalmatchedwords += 1
                        if word in gutenwords or word in lexicon:
                            totalcorrectmatchedwords += 1

            else:
                unmatchedchars += snippetlen
                if not lastmatched:
                    onebeforematched = False
                lastmatched = False

        stoptime = time.time()
        elapsed = stoptime - starttime
        charspersec = round(hlen / elapsed, 2)

        spellerrorpct = round((totalmatchedwords - totalcorrectmatchedwords) / (totalmatchedwords + 1), 5)

        print(h, unmatchedchars / (matchedchars + unmatchedchars), matchedchars/ (continuations + 1), spellerrorpct, charspersec)

        rows.append((h, str(round(unmatchedchars / (matchedchars + unmatchedchars), 5)), str(round(spellerrorpct, 5))))


    with open(outfilename, mode = 'a', encoding = 'utf-8') as f:
        for row in rows:
            f.write('\t'.join(row) + '\n')

















