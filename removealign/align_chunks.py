# align_chunks.py

# The goal here is to take manually-trimmed Gutenberg text files,
# and align them with HathiTrust files (which have already had
# headers removed).

# This will produce two paired sequences of "chunks," where
# ideally each chunk begins and ends in the same place. The chunks should
# also have *roughly* the same length, which is defined by a global
# parameter CHUNKLEN that we are hard-coding to 40,000 chars for now.

# Dividing files into (roughly) equal-length segments may help us
# produce apples-to-apples comparisons later on, when we're reasoning
# about the accuracy of predictive models. Otherwise we'd have to
# deal with the possibility that text length interacts with OCR
# badness in some nonlinear way, which could be hard to control for.

# We count chunk length in characters rather than words, although the
# the character/word ratio will no doubt vary, because we're willing
# to accept 20-30% variation in the number of words. (I also suspect
# that the useful information for a predictive model is more proportional
# to character count anyway, since long words are more informative.)

# We make no effort to infer "chapters," but do try to end each chunk
# at a sentence boundary. However, we define sentence boundaries
# simply by locating a period; this is imperfect but acceptable
# for our purposes.

# The chunks are named for the Gutenberg file, since that is
# a unique book-level identifier, and HathiTrust volume IDs are not.

# The filename protocol is GUTENID_(source)chunknum, like e.g.
# the paired third chunks of a file with Guten ID 35418 might be
# 35418_guten2 and 35418_hathi2. Zero-indexed of course.

import os, csv, sys
from difflib import SequenceMatcher

# At the moment, I point this script at volumes by manually
# creating a dictionary where keys are Gutenberg IDs
# and values are a list of Hathitrust IDs.

idmap = {'52603': ['uiuo.ark+=13960=t0pr84q15', 'uiuo.ark+=13960=t74t6zh4r'],
'41256': ['nyp.33433074864178'],
'35418': ['uc1.b4578709'],
'49332': ['uc2.ark=+13960+t8z897s8x']}

# When we scale up, we can get this from Wenyi's "updated" .tsvs
# that he createdafter downloading Hathi text.

# Right now the script expects to find Gutenberg texts and
# Hathitrust *text files* (not .tar files) in the two directories
# below, which should be in the same folder as this script:

gutendir = 'cleanguten/'
hathidir = 'hathiheadless/'

# It wants to send its output to this directory, also in the same
# folder as this script.

# Hathiheadless contains Hathi files that have already passed
# through the process of header removal

outchunkdir = 'chunks/'

# These constants are all subject to change and could be tuned:

CHUNKLEN = 40000       # minimum length of chunk in chars, will average more
MATCHLEN = 80          # length of the snippet that we try to fuzzy-match
                       # in aligning chunks

match_threshold = 0.7    # needs tuning

# Check to see if we can overwrite an existing metadata file,
# or if we need to create a header for one.

# This keeps track of the phrases aligned and the goodness of
# match.

fieldnames = ['title', 'gposition', 'hposition', 'gmatch', 'hmatch', 'quality',
'guten_chunklen', 'hathi_chunklen', 'guten_charsleft', 'hathi_charsleft', 'comments']

if os.path.exists('chunkalignmentmeta.tsv'):
    overwrite = input('Overwrite existing alignment metadata (y/n)? ')
    if overwrite.lower().strip() == 'y':
        overwrite = True
    else:
        overwrite = False
else:
    overwrite = True

if overwrite:
    with open('chunkalignmentmeta.tsv', mode = 'w', encoding = 'utf-8') as f:
        scribe = csv.DictWriter(f, fieldnames = fieldnames, delimiter = '\t')
        scribe.writeheader()

# The rest of this script may be easiest to read if you start from the bottom
# The main script iterates through the idmap and creates objects of type
# PairedSequence.

# For each sequence, it calls the method pair_chunks() and then the method
# write_chunks(). The pair_chunks() method calls all the functions defined below.

# In particular it usually starts by calling a function that gets a
# snippet to match from the *Gutenberg* volume, like
#     locate_match_start()  or  locate_match_end()
# Those functions in turn call other functions that try to locate a
# fuzzy match in the *Hathitrust* volume:
#     find_hathi_start()   or   find_hathi_end()
# If this is impossible, we try a different location in Gutenberg.
#
# The first alignment takes place using the *start* functions, because
# our fixed point is the first character in Gutenberg (or technically, the first
# character in the first line that contains any lowercase letter.)
#
# All subsequent alignments take place using the *end* functions, because
# we try to find a period (usually a sentence end) and align on that.
# So we're trying to find matches that *end* in the same place.

def get_breakless_backward(the_text, endposition, bitelength):
    '''
    Gets a sequence of bitelength characters from the Hathi volume
    while lowercasing, and removing any linebreaks and spaces in the original text.
    This will usually require taking *more* than bitelength characters, since
    the removal of whitespace chars will compress the string.

    It makes sense to remove whitespace because the amount of whitespace
    is hugely variable; for instance, poems in the Gutenberg texts can be indented
    with lots of spaces. In that case 80 chars from the Gutenberg text might only
    contain about 65 chars of actual text, and matching will be poor.

    This version of the function accepts an end position and tries to get
    bitelength non-whitespace characters BACKWARD. This is what we will be doing
    for all matches other than the first, because in those matches we start by
    finding a period, and then count backward from the period.
    '''

    startposition = endposition - bitelength

    initial_bite = the_text[startposition: endposition]
    newlines = initial_bite.count('\n')
    newlines += initial_bite.count(' ')
    if startposition - newlines < 0:
        fullbite = the_text[0 : endposition].replace('\n', '').replace(' ', '')
        return fullbite.lower().replace('ſ', 's')
    else:
        fullbite = the_text[startposition - newlines : endposition].replace('\n', '').replace(' ', '')
        return fullbite.lower().replace('ſ', 's')

def get_breakless_forward(the_text, startposition, bitelength):
    '''
    Gets a sequence of bitelength characters from the Hathi volume
    while lowercasing, and removing any linebreaks and spaces in the original text.
    This will usually require taking *more* than bitelength characters, since
    the removal of whitespace chars will compress the string.

    This version of the function accepts an end position and tries to take
    bitelength non-whitespace characters FORWARD from there. This is what we
    do for the first match in each text, because in that case our fixed point
    is the first character in the Gutenberg text (or technically, the first
    character in the first line that contains any lowercase letter.)
    '''

    endposition = startposition + bitelength

    if endposition > len(the_text):
        endposition = len(the_text)

    initial_bite = the_text[startposition: endposition]
    newlines = initial_bite.count('\n')
    newlines += initial_bite.count(' ')
    if endposition + newlines > len(the_text):
        fullbite = the_text[startposition: ].replace('\n', '').replace(' ', '')
        return fullbite.lower().replace('ſ', 's')
    else:
        fullbite = the_text[startposition: endposition + newlines].replace('\n', '').replace(' ', '')
        return fullbite.lower().replace('ſ', 's')

def read_hathi_ids(hathi_ids, hathidir):
    '''
    Reading Hathi texts is complicated enough to break out as a function
    because some lines represent page breaks. The list of first character
    positions is cruft here; it is used in align_books, but not actually
    used in align_chunks, because we don't produce page metadata here.
    '''

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

def find_hathi_end(hathitext, chunk2match, windowstart, windowend):
    '''
    Returns the character position in hathitext that is the end
    of the sequence most closely matching chunk2match.

    We only search from windowstart to windowend.

    Our strategy is to make a first pass at a 5-character stride across
    the file, and then a slower more precise match going char by char.
    In each case we create a list of (match_quality, position) tuples,
    then sort it and take the best position.

    In the final more precise pass, we upweight matches that end with
    exactly the same three characters, because we're trying above all
    to *end* in the same place*.
    '''

    chunklen = len(chunk2match)

    # First pass

    matchsequence = []

    for endposition in range(windowstart, windowend, 5):  # note 5-char stride

        hathimatch = get_breakless_backward(hathitext, endposition, chunklen)

        matcher = SequenceMatcher(None, chunk2match, hathimatch)
        match_quality = matcher.quick_ratio()
        if match_quality > .5:
            match_quality = matcher.ratio()
        matchsequence.append((match_quality, endposition))

    topmatches = sorted(matchsequence)
    topposition = topmatches[-1][1]

    windowstart = topposition - 25
    windowend = topposition + 25

    if windowstart < 0:
        windowstart = 0
    if windowend > len(hathitext):
        windowend = len(hathitext)

    # Second pass

    matchsequence = []

    for endposition in range(windowstart, windowend, 1):

        hathimatch = get_breakless_backward(hathitext, endposition, chunklen)

        matcher = SequenceMatcher(None, chunk2match, hathimatch)
        match_quality = matcher.ratio()

        if chunk2match[-3:] == hathimatch[-3 :]:
            match_quality += .03
        else:
            startmatcher = SequenceMatcher(None, chunk2match[-6: ], hathimatch[-6: ])
            start_quality = startmatcher.ratio()
            match_quality += start_quality / 50

        matchsequence.append((match_quality, endposition, hathimatch))

    topmatches = sorted(matchsequence)
    topposition = topmatches[-1][1]
    match_quality = topmatches[-1][0]
    topmatch = topmatches[-1][2]

    return topposition, match_quality, topmatch

def find_hathi_start(hathitext, chunk2match, windowstart, windowend):
    '''
    Returns the character position in hathitext that is the beginning
    of the sequence most closely matching chunk2match.

    We only search from windowstart to windowend.

    Our strategy is to make a first pass at a 5-character stride across
    the file, and then a slower more precise match going char by char.
    In each case we create a list of (match_quality, position) tuples,
    then sort it and take the best position.

    In the final more precise pass, we upweight matches that start with
    exactly the same three characters, because we're trying above all
    to *start* in the same place*.
    '''

    chunklen = len(chunk2match)

    # First pass

    matchsequence = []

    for startposition in range(windowstart, windowend, 5):  # note 5-char stride

        hathimatch = get_breakless_forward(hathitext, startposition, chunklen)

        matcher = SequenceMatcher(None, chunk2match, hathimatch)
        match_quality = matcher.quick_ratio()
        if match_quality > .5:
            match_quality = matcher.ratio()
        matchsequence.append((match_quality, startposition))

    topmatches = sorted(matchsequence)
    topposition = topmatches[-1][1]

    windowstart = topposition - 25
    windowend = topposition + 25

    if windowstart < 0:
        windowstart = 0
    if windowend > len(hathitext):
        windowend = len(hathitext)

    # Second pass

    matchsequence = []

    for startposition in range(windowstart, windowend, 1):

        hathimatch = get_breakless_forward(hathitext, startposition, chunklen)

        matcher = SequenceMatcher(None, chunk2match, hathimatch)
        match_quality = matcher.ratio()

        if chunk2match[0:3].lower() == hathimatch[0:3].lower():
            match_quality += .03
        else:
            startmatcher = SequenceMatcher(None, chunk2match[0: 6], hathimatch[0: 6])
            start_quality = startmatcher.ratio()
            match_quality += start_quality / 100

        matchsequence.append((match_quality, startposition, hathimatch))

    topmatches = sorted(matchsequence)
    if len(topmatches) < 3:
        print('window anomaly: ', windowstart, windowend)
    topposition = topmatches[-1][1]
    match_quality = topmatches[-1][0]
    topmatch = topmatches[-1][2]

    return topposition, match_quality, topmatch

def locate_match_start(gutentext, hathitext, gtarget, htarget, gradius, hradius):

    '''
    This function considers different locations in the *GUTENBERG* text as possible
    sources of a snippet to match to Hathi. It starts with one defined by gtarget,
    but if an adequate match cannot be found (adequate as defined by match_threshold),
    it considers other options.
    '''

    global match_threshold, MATCHLEN

    match_quality = 0

    for increment in range(0, gradius, MATCHLEN):   # how far from target

        gutenstart = gtarget + increment

        tomatch = get_breakless_forward(gutentext, gutenstart, MATCHLEN)

        windowstart = htarget - hradius
        if windowstart < 0:
            windowstart = 0
        elif windowstart > len(hathitext):
            windowstart = len(hathitext) - 10

        windowend = htarget + hradius
        if windowend < 0:
            windowend = 0
        elif windowend > len(hathitext):
            windowend = len(hathitext)

        matchposition, match_quality, topmatch = find_hathi_start(hathitext, tomatch, windowstart, windowend)

        if match_quality > match_threshold:  # ARBITRARY THRESHOLD
            print('match quality: ', match_quality)
            break
        elif match_quality > 0.5:
            print('Near-match that failed at: ', match_quality)
            print(tomatch)
            print('--- was not believed to match ---')
            print(topmatch)
            print()
        else:
            pass

    if match_quality < match_threshold:
        print('failure to match')
        matchposition = -1        # this is a lazy form of error propagation

    return gutenstart, matchposition, match_quality

def locate_match_end(gutentext, hathitext, gtarget, htarget, gradius, hradius):

    '''
    This function considers different locations in the *GUTENBERG* text as possible
    sources of a snippet to match to Hathi. It starts with one defined by gtarget,
    but if an adequate match cannot be found (adequate as defined by match_threshold),
    it considers other options.
    '''

    global match_threshold, MATCHLEN

    match_quality = 0

    # The following two nested loops have the effect of checking for a match,
    # initially right at gtarget, and then at increasingly remote locations,
    # alternately after and before gtarget, up to a limit provided by
    # gradius.

    for increment in range(0, gradius, MATCHLEN):   # how far from target
        for sign in [1, -1]:
            if increment == 0 and sign == -1:
                continue
            target_this_pass = gtarget + (sign * increment)

            if target_this_pass < 0:
                continue
            if target_this_pass > len(gutentext):
                target_this_pass = len(gutentext)

            # If we're in the middle of the book, we try to end the chunk at a period

            if target_this_pass + 400 < len(gutentext):
                gutenend  = gutentext.find('.', target_this_pass - 200, target_this_pass + 400) + 1
                if gutenend < 0:   # the find operation failed because there is no period
                    gutenend = target_this_pass
            else:
                gutenend = target_this_pass

                # But if we're near the end of the book we're less picky.

            tomatch = get_breakless_backward(gutentext, gutenend, MATCHLEN)

            windowstart = htarget - hradius
            if windowstart < 0:
                windowstart = 0
            elif windowstart > len(hathitext):
                windowstart = len(hathitext) - 10

            windowend = htarget + hradius

            if windowend > len(hathitext):
                windowend = len(hathitext)

            matchposition, match_quality, topmatch = find_hathi_end(hathitext, tomatch, windowstart, windowend)  # this function searches the hathi text for the specified match

            if match_quality > match_threshold:  # ARBITRARY THRESHOLD
                print('match quality: ', match_quality)
                break
            elif match_quality > 0.5:
                print('Near-match that failed at: ', match_quality)
                print(tomatch)
                print('--- was not believed to match ---')
                print(topmatch)
                print()
            else:
                pass

        if match_quality > match_threshold:
            break

    if match_quality < match_threshold:
        print('failure to match')
        matchposition = -1         # this is a lazy form of error propagation

    return gutenend, matchposition, match_quality

class PairedSequence:

    '''
    The central class in this script.
    '''

    def __init__(self, gutentext, hathitext, title_id):
        self.gutentext = gutentext
        self.hathitext = hathitext
        self.title_id = title_id

    def pair_chunks(self, chunklen, MATCHLEN):

        self.gutenchunks = []
        self.hathichunks = []

        gutenlength = len(self.gutentext)
        hathilength = len(self.hathitext)

        # We want to produce chunks of *roughly* chunklen,
        # but we also want to use the whole Gutenberg text.

        # The solution I've adopted is to split the remainder
        # across the chunks.

        if gutenlength > chunklen:
            chunks_in_guten = gutenlength // chunklen
            remainder = gutenlength - (chunks_in_guten * chunklen)
            gutenstride = chunklen + int(remainder / chunks_in_guten)
        elif gutenlength > 10000:    # imposes a hard minimum of 10000 on chunklen
            gutenstride = gutenlength
        else:
            print('This volume is too short to chunk.')
            return []

        print("Expected chunk length for volume: ", gutenstride)

        # We want to give the start and end of chunks in Gutenberg
        # the ability to move a limited distance front or back if needed

        gradius = int(gutenstride / 4)

        # In finding a Hathi match, we might need to range more widely

        hradius = int(gutenstride / 2)

        # Also, it's very common that we will need more flexibility in the
        # first match, because the story may not start until after a number
        # of Hathi pages. So we increase the hradius for the first match

        gchunkstart, hchunkstart, startmatchquality = locate_match_start(self.gutentext, self.hathitext,
            gtarget = 0, htarget = 0, gradius = gradius, hradius = hradius * 4)

        g_charsleft = gutenlength
        h_charsleft = hathilength

        errorstatus = 'none'

        matchmeta = []
        thismeta = dict()
        thismeta['title'] = self.title_id
        thismeta['gposition'] = gchunkstart
        thismeta['hposition'] = hchunkstart
        thismeta['gmatch'] = gutentext[gchunkstart : gchunkstart + MATCHLEN]
        thismeta['hmatch'] = hathitext[hchunkstart : hchunkstart + MATCHLEN]
        thismeta['quality'] = startmatchquality
        thismeta['guten_chunklen'] = 0
        thismeta['hathi_chunklen'] = 0
        thismeta['guten_charsleft'] = gutenlength
        thismeta['hathi_charsleft'] = hathilength
        thismeta['comments'] = ''
        matchmeta.append(thismeta)

        print('gposition:', gchunkstart)
        print('hposition:', hchunkstart)
        print()

        while g_charsleft > 10000:  # this imposes a hard minimum to chunklen

            gtarget = gchunkstart + gutenstride

            if gtarget + 1000 > gutenlength:
                gtarget = gutenlength

            print('Target position for this match:', gtarget)

            gchunkend, hchunkend, endmatchquality = locate_match_end(self.gutentext, self.hathitext,
                gtarget = gtarget, htarget = hchunkstart + gutenstride, gradius = gradius, hradius = hradius)

            if hchunkend < 0:
                print('failed to match the remainder')
                print()
                return matchmeta

            gchunk = self.gutentext[gchunkstart: gchunkend]
            hchunk = self.hathitext[hchunkstart: hchunkend]

            self.gutenchunks.append(gchunk)
            self.hathichunks.append(hchunk)

            gchunkstart = gchunkend
            hchunkstart = hchunkend

            print('gposition:', gchunkstart)
            print('hposition:', hchunkstart)

            g_charsleft = gutenlength - gchunkstart
            print('Characters left in guten: ', g_charsleft)
            print()

            # Now we recalculate chunk length

            if g_charsleft > chunklen:
                chunks_in_guten = g_charsleft // chunklen
                remainder = g_charsleft - (chunks_in_guten * chunklen)
                gutenstride = chunklen + int(remainder / chunks_in_guten)
            elif g_charsleft > 10000:
                gutenstride = g_charsleft
            else:
                pass
                # this tail end of the Gutenberg file will be ignored

            thismeta = dict()
            thismeta['title'] = self.title_id
            thismeta['gposition'] = gchunkstart
            thismeta['hposition'] = hchunkstart
            thismeta['gmatch'] = gchunk[-MATCHLEN : ]
            thismeta['hmatch'] = hchunk[-MATCHLEN : ]
            thismeta['quality'] = endmatchquality
            thismeta['guten_chunklen'] = len(gchunk)
            thismeta['hathi_chunklen'] = len(hchunk)
            thismeta['guten_charsleft'] = g_charsleft
            thismeta['hathi_charsleft'] = hathilength - hchunkstart
            thismeta['comments'] = ''
            matchmeta.append(thismeta)

        return matchmeta

    def write_chunks(self, outchunkdir):

        outhathipath = outchunkdir + str(self.title_id) + '_hathi'
        outgutenpath = outchunkdir + str(self.title_id) + '_guten'

        for idx, chunk in enumerate(self.gutenchunks):
            with open(outgutenpath + str(idx) + '.txt', mode = 'w', encoding = 'utf-8') as f:
                f.write(chunk)

        for idx, chunk in enumerate(self.hathichunks):
            with open(outhathipath + str(idx) + '.txt', mode = 'w', encoding = 'utf-8') as f:
                f.write(chunk)


# MAIN EXECUTION STARTS HERE

allmeta = []

for guten_id, hathi_ids in idmap.items():
    print()
    print('Gutenberg title ID:', guten_id)
    print('Being matched to: ', hathi_ids)

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

    firstcharpositionsforpages, hathitext = read_hathi_ids(hathi_ids, hathidir)

    thisseq = PairedSequence(gutentext, hathitext, guten_id)

    matchmeta = thisseq.pair_chunks(CHUNKLEN, MATCHLEN)  # constants set at the top of script

    allmeta.extend(matchmeta)

    thisseq.write_chunks(outchunkdir)

    with open('chunkalignmentmeta.tsv', mode = 'a', encoding = 'utf-8') as f:
        scribe = csv.DictWriter(f, fieldnames = fieldnames, delimiter = '\t')
        for row in matchmeta:
            scribe.writerow(row)




















