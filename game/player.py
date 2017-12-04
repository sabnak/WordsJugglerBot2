from libs.dbAdapter import DB
import logging


class Player:

	@staticmethod
	def getId(playerInfo):
		player = DB.getOne("SELECT id FROM player WHERE telegram_id = %(telegram_id)s", dict(telegram_id=playerInfo['id']))
		return player['id'] if player else Player._addPlayer(playerInfo)

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
			SELECT *
			FROM player
			JOIN word ON (player_id = player.id)
			WHERE round_id = %(round_id)s AND game_id = %(game_id)s AND word = %(word)s
		""", params)

	@staticmethod
	def _addPlayer(playerInfo):
		name = Player._buildPlayerName(playerInfo)
		player_id = DB.execute(
			"INSERT INTO player SET name = %(name)s, telegram_id = %(telegram_id)s", dict(name=name, telegram_id=playerInfo.id)).lastrowid
		logging.info("Player '%s' was added. ID: %s" % (name, player_id))
		return player_id

	@staticmethod
	def _buildPlayerName(playerInfo):
		return playerInfo.first_name

