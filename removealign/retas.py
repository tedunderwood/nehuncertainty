# retas.py

# based on the Recursive Text Alignment Scheme
# proposed by Yalniz and Manmatha
# http://www.iapr-tc11.org/archive/icdar2011/fileup/PDF/4520a754.pdf

import re
from difflib import SequenceMatcher

def get_indexes(stringlist):

    counter = 0
    indexes = []
    for s in stringlist:
        indexes.append(counter)
        counter += len(s)

    return indexes


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

        self.gindexes = get_indexes(gutenwords)
        self.hindexes = get_indexes(hathiwords)



