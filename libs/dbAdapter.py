from sqlalchemy import create_engine
import sys
from libs.coll import Config
import json
from collections import OrderedDict

sys.setrecursionlimit(3000)


class dbAdapter:
	__INSTANCE = None

	def __new__(cls, params=None):
		if dbAdapter.__INSTANCE is None:
			dbAdapter.__INSTANCE = object.__new__(cls)
			conn = '%(adapter)s://%(username)s:%(password)s@%(host)s/%(database)s?charset=utf8'
			dbAdapter.__INSTANCE.db = create_engine(conn % params, pool_recycle=60)
			dbAdapter.__INSTANCE.db.execute("SET SESSION wait_timeout = 115200")
		'''
		rows = dbAdapter.__INSTANCE.db.execute("SELECT CONNECTION_ID() as id;")
		for id in rows:
			print(dict(id))
			q = "SELECT * FROM INFORMATION_SCHEMA.PROCESSLIST WHERE ID = %d" % id['id']
			print(q)
			rows = dbAdapter.__INSTANCE.db.execute(q)
			for process in rows:
				pr(dict(process))
			# rows = dbAdapter.__INSTANCE.db.execute("SELECT SLEEP(5)")
		'''
		return dbAdapter.__INSTANCE.db


class DB:

	@staticmethod
	def execute(query, params=None):
		q = dbAdapter()
		return q.execute(query, {} if not params else params)

	@staticmethod
	def getAll(query, params=None, jsonFields=None):
		rows = DB.execute(query, params=params)
		for row in rows:
			row = dict(row)
			if jsonFields:
				for fieldName in jsonFields:
					if fieldName in row:
						row[fieldName] = json.loads(row[fieldName], object_pairs_hook=OrderedDict)
			yield row

	@staticmethod
	def getList(query, params=None, jsonFields=None):
		rows = DB.getAll(query, jsonFields=jsonFields, params=params)
		result = []
		for row in rows:
			result.append(row)
		return result

	@staticmethod
	def getOne(query, params=None, jsonFields=None):
		rows = DB.getAll(query, jsonFields=jsonFields, params=params)
		for row in rows:
			return row
		return None


dbAdapter(dict(
	adapter=Config.get('DB.adapter'),
	host=Config.get('DB.host'),
	username=Config.get('DB.username'),
	password=Config.get('DB.password'),
	database=Config.get('DB.database'),
))
