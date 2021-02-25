# retas.py

# based on the Recursive Text Alignment Scheme
# proposed by Yalniz and Manmatha
# http://www.iapr-tc11.org/archive/icdar2011/fileup/PDF/4520a754.pdf

import re
from difflib import SequenceMatcher
from collections import Counter

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

def get_indexes(stringlist):

    counter = 0
    indexes = []
    for s in stringlist:
        indexes.append(counter)
        counter += len(s)

    return indexes

failures = []

def recursive_split(clean_words, clean_indices, ocr_words, ocr_indices):

    global failures

    '''
    Find unique words in the clean list, then (from that list) find ones
    that match the ocr_words. If we have multiple matches, choose the one
    closest to the middle of the clean text.

    Then divide both texts at the match point, and call the recursive_split
    function for both of them.

    If this process fails to produce a unique word, or one sufficiently near
    the middle of the clean text, return the
    '''

    clean_counts = Counter(clean_words)

    count_indexes = []

    ocr_set = set(ocr_words)

    cleanlength = len(clean_words)
    ocrlength = len(ocr_words)

    for word, count in clean_counts.items():
        if count != 1 or len(word) < 5:
            continue
        elif word not in ocr_set:
            continue
        elif ocr_words.count(word) > 1:
            continue
        else:

            cloc4word = clean_words.index(word)
            oloc4word = ocr_words.index(word)

            cleancontext = ""
            ocrcontext = ""

            if cloc4word > 2 and oloc4word > 3:
                cleancontext = ''.join(clean_words[(cloc4word - 3) : cloc4word])
                ocrcontext = ' '.join(ocr_words[(oloc4word - 3) : oloc4word])

            cleancontext = cleancontext + " " + word + " "
            ocrcontext = ocrcontext + " " + word + " "

            if (cleanlength - cloc4word) > 3 and (ocrlength - oloc4word) > 3:
                cleancontext = cleancontext + ''.join(clean_words[cloc4word: (cloc4word + 3)])
                ocrcontext = ocrcontext + ''.join(ocr_words[oloc4word: (oloc4word + 3)])

            matcher = SequenceMatcher(None, cleancontext, ocrcontext)
            match_quality = matcher.quick_ratio()


            if match_quality > 0.65:

                count_indexes.append((word, clean_words.index(word)))

            else:

                failures.append((cleancontext, ocrcontext))

    if len(count_indexes) < 1:
        return (-1, -1)

    midpoint = cleanlength / 2

    # these seem like unlikely defaults

    closest = 1000000
    closest_index = -1
    closest_word = 'jabberwock'

    for word, idx in count_indexes:

        proximity = abs(idx - midpoint)
        if proximity < closest:
            closest = proximity
            closest_index = idx
            closest_word = word

    if closest > (cleanlength/3):  # we stop splitting if we can't find a place in the middle
        return (-1, -1)

    else:

        ocr_midpoint = ocr_words.index(closest_word)
        clean_midpoint = closest_index

        first_clean_words = clean_words[0 : clean_midpoint]
        first_clean_indices = clean_indices[0: clean_midpoint]
        first_ocr_words = ocr_words[0 : ocr_midpoint]
        first_ocr_indices = ocr_indices[0 : ocr_midpoint]

        early_midpoints = recursive_split(first_clean_words, first_clean_indices,
            first_ocr_words, first_ocr_indices)

        paired_midpoints = (clean_indices[clean_midpoint], ocr_indices[ocr_midpoint])

        second_clean_words = clean_words[clean_midpoint: ]
        second_clean_indices = clean_indices[clean_midpoint: ]
        second_ocr_words = ocr_words[ocr_midpoint: ]
        second_ocr_indices = ocr_indices[ocr_midpoint: ]

        later_midpoints = recursive_split(second_clean_words, second_clean_indices,
            second_ocr_words, second_ocr_indices)

        midpointlist = []

        if early_midpoints != (-1, -1):
            midpointlist.extend(early_midpoints)

        midpointlist.append(paired_midpoints)

        if later_midpoints != (-1, -1):
            midpointlist.extend(later_midpoints)

        return midpointlist


class TwoTexts:

    def __init__(self, gutentext, hathitext):
        '''
        We initially get the Gutenberg and Hathi texts as two strings.
        Because recursive alignment is based on unique words, we need
        to break both strings up into sets of words. However, we also want
        to preserve the character indexes for the start of each word.
        '''

        self.gutenwords = re.split('(\W)', gutentext)
        self.hathiwords = re.split('(\W)', hathitext)

        self.gindexes = get_indexes(self.gutenwords)
        self.hindexes = get_indexes(self.hathiwords)

    def align(self):

        aligned_indexes = recursive_split(self.gutenwords, self.gindexes, self.hathiwords,
         self.hindexes)

        return aligned_indexes


idmap = {'52603': ['uiuo.ark+=13960=t0pr84q15', 'uiuo.ark+=13960=t74t6zh4r'],
'41256': ['nyp.33433074864178'],
'35418': ['uc1.b4578709'],
'49332': ['uc2.ark=+13960+t8z897s8x']}

gutendir = 'cleanguten/'
hathidir = 'hathiheadless/'

# Hathiheadless contains Hathi files that have already passed
# through the process of header removal

outchunkdir = 'retasmeta/'

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

    thistext = TwoTexts(gutentext, hathitext)

    aligned_points = thistext.align()

    break





