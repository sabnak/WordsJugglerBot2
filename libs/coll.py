import re
from collections import OrderedDict
from numpy import array
from numpy.random import choice
import configparser
import os
import pprint
import argparse


class Config:

	values = dict()

	@staticmethod
	def build():
		Config.values = configparser.ConfigParser()
		Config.values.read("./config/local.cfg")

	@staticmethod
	def get(path):
		section, name = path.split(".")
		try:
			if section:
				return Config.values[section][name]
		except KeyError:
			return os.environ.get("%s.%s" % (section, name), None)


class P(pprint.PrettyPrinter):

	def __init__(self, *args, **kwargs):
		pprint.PrettyPrinter.__init__(self)
		self.maxLength = None

	def _format(self, object, stream, indent, allowance, context, level):
		if isinstance(object, (str, bytes)):
			if self.maxLength and len(object) > self.maxLength:
				object = object[:self.maxLength] + ('...' if isinstance(object, str) else b'...')
		if isinstance(object, list) and self.maxLength and len(object) > self.maxLength:
			object = object[:self.maxLength]
		return pprint.PrettyPrinter._format(self, object, stream, indent, allowance, context, level)

	def setMaxLength(self, value):
		self.maxLength = int(value)


class ArgumentParserError(Exception):
	pass


class ThrowingArgumentParser(argparse.ArgumentParser):
	def error(self, message):
		raise ArgumentParserError(message)

	def exit(self, status=0, message=None):
		pass


def parseStringArgs(string, argsList):
	"""
	Pars string into command line arguments
	:param string: str
	:param argsList: args list
	:return dict with parsed data
	"""
	parser = ThrowingArgumentParser()
	for arg in argsList:
		parser.add_argument(*arg['name'], **arg['params'] if 'params' in arg else {})
	return vars(parser.parse_args(re.split(r'[\s\xA0]+', string) if isinstance(string, str) else string))


def pr(var, label='', toVar=False, maxLength=None):
	pp = P(indent=1)
	if maxLength:
		pp.setMaxLength(maxLength)
	if toVar:
		return pp.pformat(var)
	pp.pprint(var)


def pf(*args, **kwargs):
	return pr(*args, toVar=True, **kwargs)

def addDict(filePath):
	words = []
	rebuildedDict = filePath.replace('.txt', '_reb.txt')
	with open(filePath, "r") as f:
		for line in f:
			word = re.search(r"^[\s]+([А-ЯЁ]{3,})", line)
			if not word:
				continue
			words.append(word.groups(0))
	with open(rebuildedDict, "w") as f:
		for word in words:
			f.write("%s\n" % word)


def splitList(l, n):
	n = max(1, n)
	return [l[i:i+n] for i in range(0, len(l), n)]


def simpleDictMerge(x, y):
	z = x.copy()
	z.update(y)
	return z


def bestOfMultiple(words, weights, maxWeight=.80, percentPerPoint=5):
	weightsDict = OrderedDict([words[x], [x, y]] for x, y in enumerate([1 / len(words)] * len(words)))
	pointsDict = dict()
	minWeight = (1 - maxWeight) / (len(words) - 1)
	for weightsParsed in weights.values():
		for word, weight in weightsParsed:
			if word not in pointsDict:
				pointsDict[word] = 0
			pointsDict[word] += int(weight)
			for w, k in weightsDict.items():
				if w == word:
					weightsDict[word][1] += percentPerPoint * int(weight) / 100
				else:
					weightsDict[w][1] -= percentPerPoint * int(weight) / 100 / (len(words) - 1)
	weights = array([x[1] for x in weightsDict.values()])
	for i, weight in enumerate(weights):
		# weights[i] += weights[i]/100*100
		if weight > maxWeight:
			weights[i] = maxWeight
		if weight < minWeight:
			weights[i] = minWeight
	weights /= weights.sum()
	winner = choice(words, p=weights, replace=False)
	return winner, dict(words=words, points=pointsDict, weights=OrderedDict([word, [info[0], weights[info[0]]]] for word, info in weightsDict.items()))


def bestOfMultipleSmart(words, weights, m=.90, e=3):
	minWeight = (1 - m) / (len(words) - 1)
	weightsDict = OrderedDict([words[x], [x, minWeight]] for x, y in enumerate([1 / len(words)] * len(words)))
	weightSumPerWord = OrderedDict()
	weightToSpent = 1 - minWeight * len(words)
	for weightsParsed in weights.values():
		for word, weight in weightsParsed:
			if word not in weightSumPerWord:
				weightSumPerWord[word] = 0
			weightSumPerWord[word] += int(weight)
	coefficient = sum([i ** e for i in weightSumPerWord.values()]) * weightToSpent
	if not coefficient:
		coefficient = 1
	_parsedWeight = [
		(
			word,
			i[1] + weightSumPerWord[word] ** e / coefficient,
			i[1],
			weightSumPerWord[word]
		)
		for word, i in weightsDict.items()
	]
	p = list(zip(*_parsedWeight))
	p[1] = array(p[1])
	p[1] /= p[1].sum()
	winner = choice(p[0], p=p[1], replace=False)
	return (
		winner,
		dict(
			words=words,
			points=OrderedDict([(w[0], w[3]) for w in zip(*p)]),
			weights=OrderedDict([w[0], [i, w[1]]] for i, w in enumerate(zip(*p)))))


Config.build()

if __name__ == "__main__":
	_words = ['надышать', 'бульба', 'погонный', 'пирофосфат']
	_weights = {
		311: [
			('надышать', 0),
			('пирофосфат', 4)
		],
		-2: [
			('бульба', 0)
		],
		321: [
			('погонный', 4)
		],
		291: [
			('пирофосфат', 4)
		]
	}

	r = bestOfMultipleSmart(_words, _weights)
	pr(r)