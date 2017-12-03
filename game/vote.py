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
	def getWeightPerRoundByPlayer(**params):
		votesRow = DB.getAll("""
			SELECT word, player.id player_id, name, weight
			FROM vote
			JOIN word ON (word.id = vote.word_id)
			JOIN player ON (player.id = vote.player_id)
			WHERE vote.game_id = %(game_id)s AND vote.round_id = %(round_id)s
		""", params)
		parsedVotes = {}
		for voteRow in votesRow:
			if voteRow['name'] not in parsedVotes:
				parsedVotes[voteRow['name']] = []
			parsedVotes[voteRow['name']].append(voteRow)
		return parsedVotes, sum([vote['weight'] for votes in parsedVotes.values() for vote in votes])

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
	def getPlayerWeightPerGame(**params):
		votes = DB.getList("""
			SELECT word, vote.word_id, weight
			FROM vote
			JOIN word ON (word.id = vote.word_id)
			WHERE vote.game_id = %(game_id)s AND vote.player_id = %(player_id)s
		""", params)
		return {vote['word_id']: vote for vote in votes}, sum([vote['weight'] for vote in votes])

	@staticmethod
	def getPlayerWeightOverAll(**params):
		votes = DB.getList("""
			SELECT word, vote.word_id, weight
			FROM vote
			JOIN word ON (word.id = vote.word_id)
			WHERE vote.player_id = %(player_id)s
		""", params)
		return {vote['word_id']: vote for vote in votes}, sum([vote['weight'] for vote in votes])

	@staticmethod
	def getPlayerSumOfWeightPerRound(**params):
		votes = Vote.getPlayerWeightPerRoundByWord(**params)
		if not votes[0]:
			return 0
		return votes[1]

	@staticmethod
	def getPlayerSumOfWeightPerGame(**params):
		votes = Vote.getPlayerWeightPerGame(**params)
		if not votes[0]:
			return 0
		return votes[1]

	@staticmethod
	def getPlayerSumOfWeightOverall(**params):
		votes = Vote.getPlayerWeightOverAll(**params)
		if not votes[0]:
			return 0
		return votes[1]
