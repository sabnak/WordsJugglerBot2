from libs.dbAdapter import DB
import logging
from game.word import Word

class Round:

	@staticmethod
	def getId(game_id):
		_round = DB.getOne("SELECT * FROM round WHERE game_id = %(game_id)s ORDER BY number DESC LIMIT 1", dict(game_id=game_id))
		return Round._set(game_id, 1) if not _round else _round['id'] if _round['status'] == 'preparation' else Round._init(game_id)

	@staticmethod
	def get(round_id):
		return DB.getOne("SELECT * FROM round WHERE id=%(round_id)s" % dict(round_id=round_id))

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
	def _isRoundReadyToBegin(round_id):
		pass
		# if DB.getOne("SELECT * FROM round WHERE round_id = %(round_id)s ANS status = ''")

	@staticmethod
	def _init(game_id):
		params = dict(game_id=game_id)
		_round = DB.getOne("SELECT * FROM round WHERE game_id = %(game_id)s AND status = 'ended'", params)
		if _round:
			params['number'] = _round['number'] + 1
		elif not DB.getOne("SELECT * FROM round WHERE game_id = %(game_id)s LIMIT 1", params):
			params['number'] = 1
		if 'number' in params:
			round_id = Round._set(game_id, params['number'])
			logging.info("New %d round for game_id %d was started. ID: %s" % (params['number'], game_id, round_id))
			return round_id

	@staticmethod
	def _set(game_id, number):
		return DB.execute("INSERT INTO round SET game_id = %(game_id)s, number = %(number)s", dict(game_id=game_id, number=number)).lastrowid