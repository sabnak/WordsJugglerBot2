from libs.dbAdapter import DB
from collections import OrderedDict
import json


class Log:

	@staticmethod
	def save(**params):
		return DB.execute("""
		INSERT INTO log
		SET 
			game_id = %(game_id)s, 
			round_id = %(round_id)s, 
			group_id = %(group_id)s, 
			data = %(data)s,
			winnerPlayer_id = %(winnerPlayer_id)s,
			winnerWord_id = %(winnerWord_id)s
		""", params).lastrowid

	@staticmethod
	def get(groupByGame=True, log_id=None, **params):
		groupsLog = DB.getList("""
			SELECT 
				log.*, 
				round.number round_number, 
				groups.number group_number, 
				game.createDate game_createDate, 
				round.createDate round_createDate, 
				word.word winnerWord,
				player.name winnerPlayer_name
			FROM log
			JOIN round ON (round.id = log.round_id)
			JOIN game ON (game.id = log.game_id)
			JOIN groups ON (groups.id = log.group_id)
			JOIN word ON (word.id = log.winnerWord_id)
			JOIN player ON (player.id = log.winnerPlayer_id) 
			WHERE log.game_id = %(game_id)s
		""" + ((" AND id=%d" % log_id) if log_id else ""), params)
		if not groupByGame:
			return groupsLog
		gamesLog = OrderedDict()
		for groupLog in groupsLog:
			if groupLog['game_id'] not in gamesLog:
				gamesLog[groupLog['game_id']] = dict(
					createDate=groupLog['game_createDate'].strftime('%Y-%m-%d %H:%M:%S'),
					rounds=OrderedDict()
				)
			if groupLog['round_id'] not in gamesLog[groupLog['game_id']]['rounds']:
				gamesLog[groupLog['game_id']]['rounds'][groupLog['round_id']] = dict(
					createDate=groupLog['round_createDate'].strftime('%Y-%m-%d %H:%M:%S'),
					number=groupLog['round_number'],
					groups=OrderedDict()
				)
			groupLog['number'] = groupLog['group_number']
			groupLog['data'] = json.loads(groupLog['data'], object_hook=OrderedDict)
			gamesLog[groupLog['game_id']]['rounds'][groupLog['round_id']]['groups'][groupLog['group_id']] = groupLog
		return gamesLog

