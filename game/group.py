from libs.dbAdapter import DB
from collections import OrderedDict


class Group:

	@staticmethod
	def getGroups(params):
		groupsRows = DB.getAll("""
			SELECT number, word
			FROM group
			JOIN word ON (word.id = word_group.word_id)
			WHERE game_id=%(game_id)s AND round_id=%(round_id)s
		""", params)
		groups = OrderedDict()
		for groupRow in groupsRows:
			if groupRow['number'] not in groups:
				groups[groupRow['number']] = []
			groups[groupRow['number']].append(groupRow['word'])
		return groups

	@staticmethod
	def addWordToGroup(params):
		lastGroupNumber = Group._getLastGroupNumber(params)
		DB.execute("INSERT INTO group SET word_id=%(word_id)s, game_id=%(game_id)s, round_id=%(round_id)s, number=%(number)s", params)

	@staticmethod
	def _getLastGroupNumber(params):
		return DB.getOne("SELECT * FROM group WHERE round_id = %(round_id)s", params)
