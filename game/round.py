from libs.dbAdapter import DB
import logging
from game.word import Word


class Round:

	STATUS_PREPARATION = "preparation"
	STATUS_IN_PROGRESS = "in progress"
	STATUS_ENDED = "ended"

	@staticmethod
	def getId(game_id):
		return Round._init(game_id)

	@staticmethod
	def get(round_id):
		return DB.getOne("SELECT * FROM round WHERE id=%(round_id)s" % dict(round_id=round_id))

	@staticmethod
	def getLast(**params):
		return DB.getOne("SELECT * FROM round WHERE game_id=%(game_id)s ORDER BY id DESC LIMIT 1", params)

	@staticmethod
	def getByGame(game_id):
		roundList = DB.getList("""
			SELECT *,
			(
				SELECT count(*)
				FROM word
				WHERE round_id = round.id
			) words
			FROM round
			WHERE game_id=%(game_id)s
		""" % dict(game_id=game_id))
		for _round in roundList:
			players = DB.getList("""
				SELECT name, count(*) count
				FROM word
				JOIN player ON (player.id = player_id)
				WHERE round_id = %(round_id)s
				GROUP by player_id
			""", dict(round_id=_round['id']))
			_round['players'] = {w['name']: w['count'] for w in players}
		return roundList

	@staticmethod
	def getWordsListByAuthor(round_id):
		plainWorldsList = Word.getListByRoundId(round_id, fullAccess=True)
		parsedWordsList = {}
		for row in plainWorldsList:
			if row['telegram_id'] not in parsedWordsList:
				parsedWordsList[row['telegram_id']] = [row['name'], []]
			parsedWordsList[row['telegram_id']][1].append(row['word'])
		return parsedWordsList

	@staticmethod
	def updateRoundStatus(**params):
		DB.execute("UPDATE round SET status=%(status)s WHERE id = %(round_id)s", params)

	@staticmethod
	def _init(game_id):
		params = dict(game_id=game_id, status=Round.STATUS_ENDED)
		lastRound = DB.getOne("SELECT * FROM round WHERE game_id = %(game_id)s ORDER BY number DESC LIMIT 1", dict(game_id=game_id))
		if not lastRound:
			round_id = Round._start(game_id=game_id, number=1)
			logging.info("New %d round for game_id %d was started. ID: %s" % (1, game_id, round_id))
			Round._registerRoundInGame(game_id=game_id, round_id=round_id)
			return round_id
		if lastRound['status'] != Round.STATUS_ENDED:
			return lastRound['id']
		params['number'] = lastRound['number'] + 1
		if not DB.getOne("SELECT * FROM round WHERE game_id = %(game_id)s LIMIT 1", params):
			params['number'] = 1
		if 'number' in params:
			round_id = Round._start(game_id=game_id, number=params['number'])
			logging.info("New %d round for game_id %d was started. ID: %s" % (params['number'], game_id, round_id))
			Round._registerRoundInGame(game_id=game_id, round_id=round_id)
			return round_id

	@staticmethod
	def _registerRoundInGame(**params):
		DB.execute("""
			INSERT INTO game_has_round
			SET
				game_id = %(game_id)s,
				round_id = %(round_id)s
		""", params)

	@staticmethod
	def _start(**params):
		return DB.execute("INSERT INTO round SET game_id = %(game_id)s, number = %(number)s", params).lastrowid