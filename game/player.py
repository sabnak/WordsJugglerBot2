from libs.dbAdapter import DB
import logging
from libs.coll import Config, md5


class Player:

	@staticmethod
	def getId(playerInfo):
		player = DB.getOne("SELECT id FROM player WHERE telegram_id = %(telegram_id)s", dict(telegram_id=playerInfo['id']))
		return player['id'] if player else Player.add(playerInfo)

	@staticmethod
	def get(**params):
		player = DB.getOne("""
			SELECT
				player.*,
				series.name series_name,
				series_has_player.password series_password,
				game_has_player.password game_password,
				series_has_player.role series_role,
				game_has_player.role game_role
			FROM player
			LEFT JOIN series ON (series.id = player.series_id)
			LEFT JOIN game_has_player ON (game_has_player.player_id = player.id AND game_has_player.game_id = player.game_id)
			LEFT JOIN series_has_player ON (series_has_player.player_id = player.id AND series_has_player.series_id = player.series_id)
			WHERE telegram_id = %(telegram_id)s
		""", params)
		return player

	@staticmethod
	def joinGame(**params):
		DB.execute("""
			INSERT IGNORE INTO game_has_player
			SET
				game_id = %(game_id)s,
				player_id = %(player_id)s,
				role = %(role)s
		""", params)
		DB.execute("""
			UPDATE player
			SET game_id = %(game_id)s
			WHERE id = %(player_id)s
		""", params)

	@staticmethod
	def joinSeries(**params):
		DB.execute("""
			INSERT IGNORE INTO series_has_player
			SET
				series_id = %(series_id)s,
				player_id = %(player_id)s,
				role = %(role)s
		""", params)
		DB.execute("""
			UPDATE player
			SET	series_id = %(series_id)s, game_id = 0
			WHERE id = %(player_id)s
		""", params)

	@staticmethod
	def setSeriesPassword(**params):
		params['password'] = md5(params['password'] + Config.get('MISC.password_salt'))
		DB.execute("""
			UPDATE series_has_player
			SET password = %(password)s
			WHERE series_id = %(series_id)s AND player_id = %(player_id)s
		""", params)

	@staticmethod
	def getSeriesPassword(**params):
		player = DB.getOne("SELECT * FROM series_has_player WHERE player_id = %(player_id)s AND series_id = %(series_id)s", params)
		return player['password'] if player else None

	@staticmethod
	def getGamePassword(**params):
		player = DB.getOne("SELECT * FROM game_has_player WHERE player_id = %(player_id)s AND game_id = %(game_id)s", params)
		return player['password'] if player else None

	@staticmethod
	def setSeriesPassword(**params):
		DB.execute("""
			INSERT IGNORE INTO series_has_player
			SET
				series_id = %(series_id)s,
				player_id = %(player_id)s,
				password = %(password)s
			ON DUPLICATE KEY UPDATE password = %(password)s 
		""", params)

	@staticmethod
	def setGamePassword(**params):
		DB.execute("""
			INSERT IGNORE INTO game_has_player
			SET
				game_id = %(game_id)s,
				player_id = %(player_id)s,
				password = %(password)s
			ON DUPLICATE KEY UPDATE password = %(password)s 
		""", params)

	@staticmethod
	def setState(**params):
		DB.execute("""
			INSERT IGNORE INTO player_state
			SET isReady = 1, round_id = %(round_id)s, player_id = %(player_id)s
			ON DUPLICATE KEY UPDATE isReady=ABS(isReady - 1)
		""", params)
		return Player.getState(**params)

	@staticmethod
	def getState(**params):
		playerState = DB.getOne("SELECT isReady FROM player_state WHERE player_id = %(player_id)s AND round_id = %(round_id)s", params)
		return 0 if not playerState else playerState['isReady']

	@staticmethod
	def getPlayerByRound(**params):
		return DB.getList("""
			SELECT * 
			FROM player
			JOIN round ON (player_id = player.id)
			WHERE round.id = %(round_id)s
		""", params)

	@staticmethod
	def getPlayerByWord(**params):
		return DB.getOne("""
			SELECT player.*
			FROM player
			JOIN word ON (player_id = player.id)
			WHERE word.round_id = %(round_id)s AND word.game_id = %(game_id)s AND word = %(word)s
		""", params)

	@staticmethod
	def add(update):
		name = Player._buildPlayerName(update.message.chat)
		player_id = DB.execute(
			"""
				INSERT INTO player 
				SET name = %(name)s, telegram_id = %(telegram_id)s
			""", dict(name=name, telegram_id=update.message.chat.id)
		).lastrowid
		logging.info("Player '%s' was added. ID: %s" % (name, player_id))
		return player_id

	@staticmethod
	def _buildPlayerName(playerInfo):
		return playerInfo.first_name

