#!/usr/bin/env python

import numpy as np
import theano
import sys, os
import tempfile
import shutil
import argparse


# Parsing arguments
parser = argparse.ArgumentParser()
parser.add_argument("-i", "--input", dest="input_path", required=True, help="Path to the input text file.")
parser.add_argument("-n", "--ngram-size", dest="ngram_size", required=True, type=int, help="Ngram Size.")
parser.add_argument("-o", "--output", dest="output_path", help="Path to memory mapped output file.")
parser.add_argument("-t", "--output-text", dest="output_text_path", help="Path to text output file.")

# Mutually exculsive group of pruning arguments
prune_args = parser.add_mutually_exclusive_group()
prune_args.add_argument("--prune-vocab-size", dest="vocab_size", default=10000, type=int, help="Vocabulary size. (Default: 10000)")
prune_args.add_argument("--prune-threshold",  dest="threshold_count", type=int, help="Minimum number of occurances for a word to be added into vocabulary")
prune_args.add_argument("--vocab_file", dest="vocab_path", help="Path to an existing vocabulary file")

args = parser.parse_args()

# Set the default output path, if None is specified
if args.output_path is None:
	args.output_path = args.input_path + ".idx.mmap"

input_path = args.input_path			# Input text file path
output_path = args.output_path			# Output Path for memory mapped ngrams indices file
output_path_txt = args.output_text_path	# Output Path for text ngrams indices file
ngram_size = args.ngram_size			# Ngram Size




nsamples = 0
word_to_id_dict = dict()			# Word to Index Dictionary

if args.vocab_path is None:
	# Counting the frequency of the words.
	word_to_freq_dict = dict()		# Word Frequency Dictionary
	with open(input_path, 'r') as input_file:
		for line in input_file:
			line = line.strip()
			if len(line) == 0:
				continue
			tokens = line.strip().split()
			for token in tokens:
				if not word_to_freq_dict.has_key(token):
					word_to_freq_dict[token] = 1
				else:
					word_to_freq_dict[token] += 1
	# Pruning the vocabulary
	prune_threshold_count = args.threshold_count
	prune_vocab_size = args.vocab_size
	
	# Prune based on threshold
	if prune_threshold_count is not None:
		for token, freq in word_to_freq_dict.items():
			if freq < prune_threshold_count:
				del word_to_freq_dict[token]

	# Writing the vocab file and creating a word to id dictionary.
	vocab_path = input_path+".vocab" 
	word_to_id_dict['<unk>'] = 0
	word_to_id_dict['<s>'] = 1
	curr_index = 2
	with  open(vocab_path,'w') as f_vocab:
		f_vocab.write('<unk>\n<s>\n')
		tokens_freq_sorted = sorted(word_to_freq_dict, key=word_to_freq_dict.get, reverse=True)
		if prune_threshold_count is None and prune_vocab_size < len(tokens_freq_sorted):
			tokens_freq_sorted = tokens_freq_sorted[0:prune_vocab_size]
		for token in tokens_freq_sorted :
			f_vocab.write(token+"\n")
			word_to_id_dict[token]=curr_index
			curr_index = curr_index + 1
else:
	vocab_path = args.vocab_path
	with open(vocab_path,'r') as f_vocab:
		curr_index = 0
		for line in f_vocab:
			token = line.strip()
			if not word_to_id_dict.has_key(token):
				word_to_id_dict[token] = curr_index
			curr_index = curr_index + 1
		assert ( word_to_id_dict.has_key('<s>') and word_to_id_dict.has_key('<unk>')), "Missing <s> or <unk> in given vocab file"

_, tmp_path = tempfile.mkstemp(prefix='dlm.tmp.')
with open(input_path, 'r') as input_file, open(tmp_path, 'w') as tmp_file:
	next_id = 0
	for line in input_file:
		line = line.strip()
		if len(line) == 0:
			continue
		tokens = line.strip().split()
		for i in range(ngram_size - 1):
			tokens.insert(0, '<s>')
		indices = []
		for token in tokens:
			if not word_to_id_dict.has_key(token):
				token = "<unk>"
			indices.append(str(word_to_id_dict[token]))
		for i in range(ngram_size - 1, len(indices)):
			tmp_file.write(' '.join(indices[i - ngram_size + 1 : i + 1]) + "\n")
			nsamples += 1

with open(tmp_path, 'r') as data:
	fp = np.memmap(output_path, dtype='int32', mode='w+', shape=(nsamples + 1, ngram_size))
	fp[0,0] = nsamples					# number of samples
	fp[0,1] = ngram_size				# n-gram size
	fp[0,2] = len(word_to_id_dict)		# number of word types (MLP classes)
	counter = 1
	for line in data:
		tokens = line.split()
		fp[counter] = tokens
		counter = counter + 1
		if counter % 10000000 == 0:
			print counter
	print str(counter-1) + " samples mapped"
	fp.flush
	del fp

if output_path_txt is not None:
	shutil.move(tmp_path, output_path_txt)
else:
	os.remove(tmp_path)
