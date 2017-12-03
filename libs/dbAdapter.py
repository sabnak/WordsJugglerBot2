from sqlalchemy import create_engine
import sys
import configparser

sys.setrecursionlimit(3000)


class dbAdapter:
	__INSTANCE = None

	def __new__(cls, params=None):
		if dbAdapter.__INSTANCE is None:
			dbAdapter.__INSTANCE = object.__new__(cls)
			conn = '%(adapter)s://%(username)s:%(password)s@%(host)s/%(database)s?charset=utf8'
			dbAdapter.__INSTANCE.db = create_engine(conn % params, pool_size=50, max_overflow=0, pool_recycle=120, pool_timeout=120)
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
	def getAll(query, params=None):
		rows = DB.execute(query, params=params)
		for row in rows:
			yield dict(row)

	@staticmethod
	def getList(query, params=None):
		rows = DB.getAll(query, params=params)
		result = []
		for row in rows:
			result.append(row)
		return result

	@staticmethod
	def getOne(query, params=None):
		rows = DB.getAll(query, params=params)
		for row in rows:
			return row
		return None


config = configparser.ConfigParser()
config.read("./config/local.cfg")

dbAdapter(dict(
	adapter=config['DB']['adapter'],
	host=config['DB']['host'],
	username=config['DB']['username'],
	password=config['DB']['password'],
	database=config['DB']['database']
))
