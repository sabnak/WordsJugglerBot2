import re


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