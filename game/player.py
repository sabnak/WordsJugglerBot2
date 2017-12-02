from libs.dbAdapter import DB
import logging


class Player:

	@staticmethod
	def getId(playerInfo):
		player = DB.getOne("SELECT id FROM player WHERE telegram_id = %(telegram_id)s", dict(telegram_id=playerInfo.id))
		return player['id'] if player else Player._addPlayer(playerInfo)

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
