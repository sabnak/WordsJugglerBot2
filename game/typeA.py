from game.base import Base_Game
from libs.coll import bestOfMultiple


class Game(Base_Game):

	_WORDS_LIMIT = 2
	_WORD_MIN_LENGTH = 5
	_ROUNDS = {
		1:
		dict(
			minWordsPerPlayer=2,
			maxWordsPerPlayer=2,
			minWordLength=5,
			maxWordLength=15,
			maxWeightPerWord=4,
			maxWeightPerRound=8,
			minWeightPerRound=8,
			minPlayer=2,
			randomWordsLimit=2,
			groupSize=-1  # -1 is auto size
		)
	}

	def _start(self, groups):
		response = []
		for groupNumber, group in groups.items():
			winnerWord, stats = bestOfMultiple(group['words'], group['weights'])
			response += [
				"<b>Группа %d</b>" % groupNumber,
				"Баллы:\n%s" % "\n".join(["%d: %s" % (p, w) for w, p in stats['points'].items()]),
				"Вероятности:\n%s" % "\n".join(["%.2f: %s" % (p[1], w) for w, p in stats['weights'].items()]),
				"Слово-победитель: <b>%s</b>" % winnerWord
			]
		return response


