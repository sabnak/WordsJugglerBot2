from game.base import Base_Game
from game.round import Round


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
			maxWeightPerRound=8,
			minWeightPerRound=8,
			minPlayer=2
		)
	}

	def start(self):
		pass


