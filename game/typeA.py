from game.base import Base_Game
from collections import OrderedDict


class Game(Base_Game):

	_WORDS_LIMIT = 2
	_WORD_MIN_LENGTH = 5
	_ROUNDS = {
		1:
		dict(
			minWordsPerPlayer=1,
			maxWordsPerPlayer=1,
			minWordLength=5,
			maxWordLength=15
		)
	}

	@staticmethod
	def _start():
		pass

