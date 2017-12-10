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
		return DB.getOne("SELECT * FROM game WHERE id = %(game_id)s", params)

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
			FROM game
			JOIN game_has_player ON (game_has_player.game_id = game.id)
			WHERE player_id = %(player_id)s AND series_id = %(series_id)s
			ORDER BY game.id DESC
			LIMIT 1
		""", params, jsonFields=['settings'])

	@staticmethod
	def getPlayerFirstAvailableGame(**params):
		params['status'] = Game.STATUS_IN_PROGRESS
		return DB.getOne("""
			SELECT game.*
			FROM game
			WHERE series_id = %(series_id)s AND status = %(status)s
		""", params, jsonFields=['settings'])

	@staticmethod
	def getSeriesLastGame(**params):
		return DB.getOne("""
			SELECT *
			FROM game
			WHERE series_id = %(series_id)s
			ORDER BY id DESC
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
	def getFullInfo(game_id):
		return DB.getOne("""
			SELECT game.*, round_id, round.status roundStatus, round.number roundNumber
			FROM game_has_round
			JOIN game ON (game.id = game_has_round.game_id)
			JOIN round ON (round.id = game_has_round.round_id)
			WHERE game.id = %d
			ORDER BY game_has_round.id DESC
			LIMIT 1
		""" % game_id, jsonFields=['settings'])

	@staticmethod
	def update(**params):
		return DB.execute("UPDATE game SET winner_id = %(winner_id)s, status = %(status)s WHERE id = %(game_id)s", params)