from libs.dbAdapter import DB


class Log:

	@staticmethod
	def save(**params):
		return DB.execute("""
		INSERT INTO log
		SET game_id = %(game_id)s, round_id = %(round_id)s, groupNumber = %(groupNumber)s, data = %(data)s
		""", params)

	@staticmethod
	def get(**params):
		return DB.getList("SELECT * FROM game WHERE game_id = %(game_id)s", params)
