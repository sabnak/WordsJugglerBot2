from libs.dbAdapter import DB


class Series:

	_DEFAULT_CONFIG = dict(
		maxOpenedGamesOverall=1,
		maxOpenedGamesPerPlayer=1,
		autoCreateGames=1
	)

	PLAYER_ROLE_ADMIN = "admin"
	PLAYER_ROLE_MEMBER = "member"

	@staticmethod
	def get(**params):
		return DB.getOne("""
			SELECT *
			FROM series
			WHERE id = %(series_id)s
		""", jsonFields=['settings'], params=params)

	@staticmethod
	def getList():
		return DB.getList("""
			SELECT *
			FROM series
		""", jsonFields=['settings'])
