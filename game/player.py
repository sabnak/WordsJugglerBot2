from libs.dbAdapter import DB
import logging


class Player:

	@staticmethod
	def getId(name):
		player = DB.getOne("SELECT id FROM player WHERE name = %(name)s", dict(name=name))
		return player['id'] if player else Player._addPlayer(name)

	@staticmethod
	def _addPlayer(name):
		player_id = DB.execute("INSERT INTO player SET name = %(name)s",  dict(name=name)).lastrowid
		logging.info("Player '%s' was added. ID: %s" % (name, player_id))
		return player_id
