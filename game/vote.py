from libs.dbAdapter import DB


class Vote:

	@staticmethod
	def set(**params):
		DB.execute("""
			INSERT INTO vote
			SET word_id = %(word_id)s, game_id = %(game_id)s, round_id = %(round_id)s, weight = %(weight)s, player_id = %(player_id)s
			ON DUPLICATE KEY UPDATE weight = %(weight)s
		""", params)

	@staticmethod
	def getPlayerWeightPerRoundByWord(**params):
		votes = DB.getList("""
			SELECT word, vote.word_id, weight
			FROM vote
			JOIN word ON (word.id = vote.word_id)
			WHERE vote.game_id = %(game_id)s AND vote.round_id = %(round_id)s AND vote.player_id = %(player_id)s
		""", params)
		return {vote['word_id']: vote for vote in votes}, sum([vote['weight'] for vote in votes])

	@staticmethod
	def getPlayerSumOfWeightPerRound(**params):
		votes = Vote.getPlayerWeightPerRoundByWord(**params)
		print(votes)
		if not votes[0]:
			return 0
		return votes[1]
