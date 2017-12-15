from libs.dbAdapter import DB
import logging
from game.round import Round
from game.player import Player
from game.series import Series


class Game:

	STATUS_PREPARATION = "preparation"
	STATUS_IN_PROGRESS = "in progress"
	STATUS_ENDED = "ended"

	PLAYER_ROLE_ADMIN = "admin"
	PLAYER_ROLE_MEMBER = "member"

	__id = None
	__game = None

	def create(self, **params):
		self.__id = Game._init(**params)
		self.__game = self.get(game_id=self.__id)
		return self.__game

	def join(self, game_id):
		self.__id = game_id
		self.__game = self.get(game_id=self.__id)
		return self.__game

	@staticmethod
	def get(**params):
		return DB.getOne("SELECT * FROM game WHERE id = %(game_id)s", params, jsonFields=['settings'])

	@staticmethod
	def getList(**params):
		conditions = ""
		if 'status' in params:
			conditions += " AND status IN %(status)s"
		if 'creator_id' in params:
			conditions += " AND creator_id = %(creator_id)s"
		if 'series_id' in params:
			conditions += " AND series_id = %(series_id)s"
		return DB.getList("""
			SELECT *
			FROM game
			WHERE 1
		""" + conditions, params)

	@staticmethod
	def getPlayerLastGame(**params):
		return DB.getOne("""
			SELECT game.*
			FROM player
			JOIN game ON (game.id = player.game_id)
			WHERE player_id = %(player_id)s AND player.series_id = %(series_id)s
		""", params, jsonFields=['settings'])

	@staticmethod
	def getLastGameInSeries(**params):
		condition = ""
		if 'status' in params:
			condition = " AND status IN (%(status)s)"
		return DB.getOne("""
			SELECT game.*
			FROM game
			WHERE series_id = %(series_id)s """ + condition + """
			ORDER BY game.id DESC
			LIMIT 1
		""", params, jsonFields=['settings'])

	@staticmethod
	def getPlayerAvailableGames(**params):
		params['status'] = Game.STATUS_IN_PROGRESS
		return DB.getList("""
			SELECT game.*
			FROM game
			WHERE series_id = %(series_id)s AND status = %(status)s
		""", params, jsonFields=['settings'])

	@staticmethod
	def setGamePassword(**params):
		DB.execute("UPDATE game SET password = %(password)s WHERE id = %(game_id)s", params)

	@staticmethod
	def setGameStatus(**params):
		DB.execute("UPDATE game SET status = %(status)s WHERE id = %(game_id)s", params)

	@staticmethod
	def _init(**params):
		if 'status' not in params:
			params['status'] = Game.STATUS_PREPARATION
		game_id = DB.execute("""
			INSERT INTO game
			SET
				creator_id = %(player_id)s,
				status = %(status)s,
				settings = %(settings)s,
				series_id = %(series_id)s
		""", params).lastrowid
		logging.info("New game was started. ID: %d" % game_id)
		Round.getId(game_id)

		params['role'] = Series.PLAYER_ROLE_MEMBER if 'seriesRole' not in params else params['seriesRole']
		Player.joinSeries(**params)

		params['role'] = Game.PLAYER_ROLE_ADMIN if 'gameRole' not in params else params['gameRole']
		Player.joinGame(game_id=game_id, **params)

		return game_id

	@staticmethod
	def getFullInfo(**params):
		return DB.getOne("""
			SELECT game.*, round_id, round.status roundStatus, round.number roundNumber
			FROM game_has_round
			JOIN game ON (game.id = game_has_round.game_id)
			JOIN round ON (round.id = game_has_round.round_id)
			WHERE game.id = %(game_id)s
			ORDER BY game_has_round.id DESC
			LIMIT 1
		""", params, jsonFields=['settings'])

	@staticmethod
	def updateSettings(**params):
		return DB.execute("UPDATE game SET settings = %(settings)s WHERE id = %(game_id)s", params)

	@staticmethod
	def update(**params):
		return DB.execute("UPDATE game SET winner_id = %(winner_id)s, status = %(status)s WHERE id = %(game_id)s", params)