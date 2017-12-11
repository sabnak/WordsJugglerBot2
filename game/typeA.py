from game.base import Base_Game
from libs.coll import bestOfMultipleSmart


class Game(Base_Game):

	_SETTINGS = dict(
		round={
			1:
			dict(
				minWordsPerPlayer=1,
				maxWordsPerPlayer=1,
				minWordLength=4,
				maxWordLength=15,
				maxWeightPerWord=4,
				maxWeightPerRound=4,
				minWeightPerRound=4,
				minPlayers=3,
				maxPlayers=20,
				randomWordsLimit=2,
				percentPerPoint=5,
				groupSize=-1,  # -1 is auto size
				fightDegree=3.0,
				fightMaxWeight=.9,
				validationRegex=""
			)
		}
	)

	def _start(self, words, weights):
		winnerWord, stats = bestOfMultipleSmart(words, weights)
		return winnerWord, stats


