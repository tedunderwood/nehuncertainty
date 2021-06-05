Textual mismatch between dirty chunks and the clean volume
==========================================================

The five ```nocorrerrs``` files here provide information about dirty chunks that can be used to estimate distortion in our analysis notebooks.

The python script is the code that produced them.

They're called "no correlation errors" because I changed the alignment script so that it didn't measure "word errors" on segments where we already got a "passage fail" in fuzzy matching.

The logic here probably needs more work, but it will suffice for a first pass, to give us a sense of the scale of the problem.

