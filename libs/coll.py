import re
from collections import OrderedDict
from numpy import array
from numpy.random import choice


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

def bestOfMultiple(words, weights, maxWeight=.80):
	weightsDict = OrderedDict([words[x], [x, y]] for x, y in enumerate([1 / len(words)] * len(words)))
	pointsDict = dict()
	minWeight = (1 - maxWeight) / (len(words) - 1)
	print(minWeight)
	for author, weightsString in weights.items():
		weightsParsed = re.findall(r"(?P<word>[А-яёA-z]+)[\s]*(?P<weight>[\d]+)", weightsString)
		for word, weight in weightsParsed:
			if word not in pointsDict: pointsDict[word] = 0
			pointsDict[word] += int(weight)
			for w, k in weightsDict.items():
				if w == word:
					weightsDict[word][1] += 5 * int(weight) / 100
				else:
					weightsDict[w][1] -= 5 * int(weight) / 100 / (len(words) - 1)
	weights = array([x[1] for x in weightsDict.values()])
	for i, weight in enumerate(weights):
		# weights[i] += weights[i]/100*100
		if weight > maxWeight: weights[i] = maxWeight
		if weight < minWeight: weights[i] = minWeight
	weights /= weights.sum()
	print("Points: ", pointsDict)
	print("Weights: ", {w: "%.3f" % weights[v[0]] for w, v in weightsDict.items()})
	iterations = 1
	games = 1
	g = 0
	while g < games:
		g += 1
		i = 0
		winners = dict()
		while i < iterations:
			winnerWord = choice(words, p=weights, replace=False)
			if winnerWord not in winners: winners[winnerWord] = 0
			winners[winnerWord] += 1
			i += 1
		print("Game %d. %d iterations:" % (g, iterations), winners)
