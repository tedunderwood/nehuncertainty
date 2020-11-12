# align_texts.py

# The goal here is to take manually-trimmed Gutenberg text files,
# and align them with HathiTrust files (which have already had
# headers removed).

# At first, this will be very simple. We'll just find the start and
# end of the guten-file inside the hathi-file, using fuzzy matching.

# Eventual complications (TODO stubs below) will be:

# 1) Multiple Hathi volumes for each Gutenberg file.

# 2) Maybe we want to break the volumes up into (aligned) 5000-word
# chunks? It's okay if the chunks aren't exactly 5000 words, so
# we can slide endpoints around a little to find good matches.

# 3) The main output of this process will be the aligned
# texts, or text-chunks, themselves. But a secondary goal is to identify
# pages of the original Hathi volume as "front matter," "narrative," or
# "back matter." We can then use the labeled pages to train
# a model that predicts the start and end of a narrative.
# This will require establishing a map of character positions in the text
# file to page numbers in the original Hathi volume.

from difflib import SequenceMatcher

# Hypothesize a dictionary where keys are Gutenberg IDs
# and values are a list of Hathitrust IDs.

idmap = {'49332': ['uc2.ark=+13960+t8z897s8x'],
'35418': ['uc1.b4578709']}

# When we scale up, we will get this from Wenyi's "updated" .tsvs
# that he createdafter downloading Hathi text. Right now,
# I'm hard-coding a single pair of volumes.

# TODO stub: write some Python here that reads
# annotatednormalizedfictionmeta-updated.tsv and
# annotatednormalizedbiometa-updated.tsv
# and converts them both into the dictionary
# idmap, according to the format seen above.
# Where Hathi ids are separated by pipes, the
# list that is the value will have len > 1.
# It's important that volumes are listed in the
# right order.

# TODO:
# We need to check that the Gutenberg texts actually exist;
# in other words, that Raina is through with them, they've been downloaded,
# and are present in the Gutnberg directory named below.

gutendir = 'cleanguten/'
hathidir = 'hathiheadless/'

outgutendir = 'trimmedguten/'
outhathidir = 'trimmedhathi/'

# hathiheadless contains Hathi files that have already passed
# through the process of header removal

def get_breakless_text(the_text, startposition, bitelength):
    '''
    Gets a sequence of 75 characters from the Hathi volume
    while removing any linebreaks in the original text.
    This may require taking *more* than 75 characters, since
    the removal of linebreaks will compress the string.

    We have to do this because the Gutenberg text generally
    includes newline characters only at the end of a paragraph.
    '''

    endposition = startposition + 75
    if endposition > len(the_text):
        return the_text[startposition : ].replace('\n', '')
    else:
        initial_bite = the_text[startposition: endposition]
        newlines = initial_bite.count('\n')
        if endposition + newlines > len(the_text):
            return initial_bite.replace('\n', '')
        else:
            return the_text[startposition : endposition + newlines].replace('\n', '')

def textcompress(atext):
    ''' Gets rid of runs of spaces, newlines, and tab characters.
    '''
    while '  ' in atext:
        atext = atext.replace('  ', ' ')

    return atext.replace('\n', '').replace('\t', '')

def read_hathi_ids(hathi_ids, hathidir):
    currentcharposition = 0
    firstcharpositionsforpages = []
    listoflines = []
    for an_id in hathi_ids:
        with open(hathidir + an_id + '.txt', encoding = 'utf-8') as f:
            for line in f:
                if line.startswith('<#PG#') and line.strip().endswith('>'):
                    firstcharpositionsforpages.append(currentcharposition)
                else:
                    listoflines.append(line)
                    currentcharposition += len(line)

    return firstcharpositionsforpages, ''.join(listoflines)


def find_match_position(hathitext, chunk2match, windowstart, windowend):
    '''
    Returns the character position in hathitext that is the beginning
    of the sequence most closely matching chunk2match.

    We only search from windowstart to windowend.

    Our strategy is to make a first pass at a 4-character stride across
    the file, and then a slower more precise match going char by char.
    In each case we create a list of (match_quality, position) tuples,
    then sort it and take the best position.
    '''

    chunklen = len(chunk2match)

    # First pass

    matchsequence = []

    for startposition in range(windowstart, windowend, 4):  # note 4-char stride

        hathimatch = get_breakless_text(hathitext, startposition, chunklen)

        matcher = SequenceMatcher(None, chunk2match, hathimatch)
        match_quality = matcher.quick_ratio()
        if match_quality > .5:
            match_quality = matcher.ratio()
        matchsequence.append((match_quality, startposition))

    topmatches = sorted(matchsequence)
    topposition = topmatches[-1][1]

    windowstart = topposition - 20
    windowend = topposition + 20

    if windowstart < 0:
        windowstart = 0
    if windowend > len(hathitext):
        windowend = len(hathitext)

    # Second pass

    matchsequence = []

    for startposition in range(windowstart, windowend, 1):

        hathimatch = get_breakless_text(hathitext, startposition, chunklen)

        matcher = SequenceMatcher(None, chunk2match, hathimatch)
        match_quality = matcher.ratio()
        matchsequence.append((match_quality, startposition))

    topmatches = sorted(matchsequence)
    topposition = topmatches[-1][1]
    match_quality = topmatches[-1][0]

    return topposition, match_quality

trimming_metadata = []

for guten_id, hathi_ids in idmap.items():
    print()
    print(guten_id)

    # In reading the Gutenberg file, we skip initial lines
    # that have only whitespace, punctuation, or uppercase letters.
    # We start with the first text line, aka line with at least
    # one lowercase letter.

    with open(gutendir + str(guten_id) + '.txt', encoding = 'utf-8') as f:
        gutenlines = f.readlines()

    gutentext = []
    startusing = False

    for line in gutenlines:
        if startusing:
            gutentext.append(line)
        elif any(c for c in line if c.islower()):
            startusing = True
            gutentext.append(line)
        else:
            pass

    gutentext = ' '.join(gutentext)

    # gutentext = textcompress(gutentext)  # gets rid of superfluous spaces and \n

    firstcharpositionsforpages, hathitext = read_hathi_ids(hathi_ids, hathidir)

    # Note that the firstcharpositionsforpages is a list where each entry
    # represents the char position in hathitext that is the first character
    # in the page corresponding to its index in the list. E.g.
    # [0, 1431, 2722, ....] means that page 0 was 1431 chars long, and
    # page 1 begins on char 1431.

    guten_length = len(gutentext)
    hathi_length = len(hathitext)

    offsetmax = 50000
    if offsetmax > guten_length / 4:
        offsetmax = int(guten_length / 4)

    for gutenstart in range(0, offsetmax, 80):
        startmatch = gutentext[gutenstart: gutenstart + 80]
        startposition, match_quality = find_match_position(hathitext, startmatch, 0, int(hathi_length / 2))
        if match_quality > .75:
            print(match_quality)
            break

    for gutenend in range(guten_length, guten_length - offsetmax, -80):
        endmatch = gutentext [gutenend - 80: gutenend]
        endposition, match_quality = find_match_position(hathitext, endmatch, int(hathi_length / 2), hathi_length)
        if match_quality > .75:
            print(match_quality, endmatch)
            break
        else:
            print(match_quality)

    lastpagestart = [x for x in firstcharpositionsforpages if x < startposition][-1]
    startpage = firstcharpositionsforpages.index(lastpagestart)

    lastpagestart = [x for x in firstcharpositionsforpages if x < endposition][-1]
    endpage = firstcharpositionsforpages.index(lastpagestart)

    trimmedgutentext = gutentext[gutenstart: gutenend]

    trimmedhathitext = hathitext[startposition: endposition + 80]

    metadatarow = dict()
    metadatarow['hathistart'] = startposition
    metadatarow['hathiend'] = endposition + 80
    metadatarow['gutenstart'] = gutenstart
    metadatarow['gutenend'] = gutenend
    metadatarow['startpage'] = startpage
    metadatarow['endpage'] = endpage

    with open(outgutendir + guten_id + '_trimmed.txt', mode = 'w', encoding = 'utf-8') as f:
        f.write(trimmedgutentext)

    with open(outhathidir + guten_id + '_trimmedhathi.txt', mode = 'w', encoding = 'utf-8') as f:
        f.write(trimmedhathitext)

    trimming_metadata.append(metadatarow)





















