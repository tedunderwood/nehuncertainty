# align_texts.py

# The goal here is to take manually-trimmed Gutenberg text files,
# and align them with HathiTrust files (which have already had
# headers removed).

# At first, this will be very simple. We'll just find the start and
# end of the guten-file inside the hathi-file, using fuzzy matching.

# Eventual complications will be:

# 1) Multiple Hathi volumes for each Gutenberg file.

# 2) Maybe we want to break the volumes up into (aligned) 5000-word
# chunks? It's okay if they aren't exactly 5000 words, so
# we can slide endpoints around a little to find good matches.


from difflib import SequenceMatcher

# Hypothesize a dictionary where keys are Gutenberg IDs
# and values are a list of Hathitrust IDs

idmap = {'49332': ['uc2.ark=+13960+t8z897s8x']}

# In practice, we will get this from Wenyi's "updated" .tsv that he created
# after downloading Hathi text.

# We will need to check that the Gutenberg texts actually exist;
# in other words, that Raina is through with them and they've been downloaded.

gutendir = 'cleanguten'
hathidir = 'hathiheadless'

# hathiheadless contains Hathi files that have already passed
# through the process of header removal
