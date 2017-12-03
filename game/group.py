from libs.dbAdapter import DB
from collections import OrderedDict


class Group:

	STATUS_DEFEAT = 'defeat'
	STATUS_VICTORY = 'victory'
	STATUS_EXILE = 'exile'
	STATUS_UNDEFINED = 'undefined'

	@staticmethod
	def getGroups(**params):
		numberCondition = " AND number = %(number)s" if 'number' in params else ""
		groupsRows = DB.getList("""
			SELECT number, word
			FROM groups
			JOIN word ON (word.id = groups.word_id)
			WHERE groups.game_id=%(game_id)s AND groups.round_id=%(round_id)s
		""" + numberCondition, params)
		groups = OrderedDict()
		for groupRow in groupsRows:
			if groupRow['number'] not in groups:
				groups[groupRow['number']] = []
			groups[groupRow['number']].append(groupRow['word'])
		return groups

	@staticmethod
	def getGroupNumberByWordId(**params):
		wordInGroup = DB.getOne("SELECT number FROM groups WHERE groups.game_id=%(game_id)s AND groups.round_id=%(round_id)s AND word_id=%(word_id)s", params)
		return wordInGroup['number'] if wordInGroup else None

	@staticmethod
	def getGroupByWord(**params):
		number = Group.getGroupNumberByWordId(**params)
		if not number:
			return None
		groups = Group.getGroups(number=number, **params)
		if not groups:
			return None
		if len(groups) > 1:
			return -1
		return groups.popitem()

	@staticmethod
	def addWordToGroup(**params):
		# lastGroupNumber = Group._getLastGroupNumber(params)
		# params['number'] = 1 if not lastGroupNumber else lastGroupNumber+1
		DB.execute("INSERT INTO groups SET word_id=%(word_id)s, game_id=%(game_id)s, round_id=%(round_id)s, number=%(number)s, status=%(status)s", params)

	@staticmethod
	def _getLastGroupNumber(params):
		return DB.getOne("SELECT * FROM groups WHERE round_id = %(round_id)s", params)
