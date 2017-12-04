from game.base import Base_Game
from libs.coll import bestOfMultiple
from game.player import Player

class Game(Base_Game):

	_WORDS_LIMIT = 2
	_WORD_MIN_LENGTH = 5
	_ROUNDS = {
		1:
		dict(
			minWordsPerPlayer=1,
			maxWordsPerPlayer=1,
			minWordLength=5,
			maxWordLength=15,
			maxWeightPerWord=4,
			maxWeightPerRound=4,
			minWeightPerRound=4,
			minPlayers=3,
			maxPlayers=6,
			randomWordsLimit=2,
			percentPerPoint=5,
			groupSize=-1  # -1 is auto size
		)
	}

	def _start(self, words, weights):
		winnerWord, stats = bestOfMultiple(words, weights, percentPerPoint=self.roundSettings['percentPerPoint'])
		response = [
			"Баллы:\n%s" % "\n".join(["%d: %s" % (p, w) for w, p in stats['points'].items()]),
			"Вероятности:\n%s" % "\n".join(["%.2f: %s" % (p[1], w) for w, p in stats['weights'].items()]),
			"Слово-победитель: <b>%s</b>" % winnerWord,
			"Игрок-победитель: <b>%s</b>" % Player.getPlayerByWord(word=winnerWord, **self.gameState)['name']
		]
		return winnerWord, stats, response


