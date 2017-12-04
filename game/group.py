from libs.dbAdapter import DB
from collections import OrderedDict


class Group:

	STATUS_DEFEAT = 'defeat'
	STATUS_VICTORY = 'victory'
	STATUS_EXILE = 'exile'
	STATUS_UNDEFINED = 'undefined'

	@staticmethod
	def getGroupWords(**params):
		groupsRows = Group.get(**params)
		groups = OrderedDict()
		for groupRow in groupsRows:
			if groupRow['number'] not in groups:
				groups[groupRow['number']] = []
			groups[groupRow['number']].append(groupRow['word'])
		return groups

	@staticmethod
	def get(groupByGroupNumber=False, **params):
		numberCondition = " AND number = %(number)s" if 'number' in params else ""
		groupsList = DB.getList("""
		SELECT groups.id, number, word, p1.id player_id, p1.name, p1.telegram_id, weight, p2.id electorPlayer_id, p2.name electorName
		FROM groups
		JOIN word ON (word.id = groups.word_id)
		JOIN player p1 ON (p1.id = word.player_id)
		LEFT JOIN vote ON (vote.word_id = groups.word_id AND vote.game_id = %(game_id)s AND vote.round_id = %(round_id)s)
		LEFT JOIN player p2 ON (p2.id = vote.player_id)
		WHERE groups.game_id = %(game_id)s AND groups.round_id = %(round_id)s
		""" + numberCondition, params)
		if not groupByGroupNumber:
			return groupsList
		groupedGroups = OrderedDict()
		for group in groupsList:
			if group['number'] not in groupedGroups:
				groupedGroups[group['number']] = []
			groupedGroups[group['number']].append(group)
		return groupedGroups

	@staticmethod
	def getGroupNumberByWordId(**params):
		wordInGroup = DB.getOne("SELECT number FROM groups WHERE groups.game_id=%(game_id)s AND groups.round_id=%(round_id)s AND word_id=%(word_id)s", params)
		return wordInGroup['number'] if wordInGroup else None

	@staticmethod
	def getGroupByWord(**params):
		number = Group.getGroupNumberByWordId(**params)
		if not number:
			return None
		groups = Group.getGroupWords(number=number, **params)
		if not groups:
			return None
		if len(groups) > 1:
			return -1
		return groups.popitem()

	@staticmethod
	def addWordToGroup(**params):
		# lastGroupNumber = Group._getLastGroupNumber(params)
		# params['number'] = 1 if not lastGroupNumber else lastGroupNumber+1
		DB.execute("INSERT INTO groups SET word_id=%(word_id)s, player_id = %(player_id)s, game_id=%(game_id)s, round_id=%(round_id)s, number=%(number)s, status=%(status)s", params)

	@staticmethod
	def _getLastGroupNumber(params):
		return DB.getOne("SELECT * FROM groups WHERE round_id = %(round_id)s", params)
