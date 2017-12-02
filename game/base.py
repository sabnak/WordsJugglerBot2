from libs.dbAdapter import DB
import re
import logging
import random
from game.player import Player
from game.word import Word
from game.round import Round


class Base_Game:

	ERROR_CODES = {
		"INNER_ERROR": "Ебануться! Что-то пошло не так. Я не смог сохранить твоё словцо. Не делай так больше!"
	}

	_ROUNDS = dict()

	_DICTIONARIES = {
		"ushakov": r"f:\WordsJugglerBot\dictionaries\ushakov_reb.txt"
	}

	game_id = None
	round_id = None
	roundNumber = None

	def _refreshGameState(self):
		self.game_id, self.round_id = self._getId()
		self.roundNumber = Round.get(self.round_id)['number']

	def addWord(self, update):
		self._refreshGameState()
		return Word.add(dict(
			word=update.message.text,
			player_id=Player.getId(update.message.chat),
			game_id=self.game_id,
			round_id=self.round_id),
			self._ROUNDS[self.roundNumber]['minWordsPerPlayer'],
			self._ROUNDS[self.roundNumber]['minWordLength']
		)

	def updateWord(self, oldWord, newWord, update):
		self._refreshGameState()
		player_id = Player.getId(update.message.chat)
		return Word.update(oldWord=oldWord, newWord=newWord, player_id=player_id, round_id=self.round_id, wordMinLength=self._ROUNDS[self.roundNumber]['minWordLength'])

	@staticmethod
	def get(game_id=None):
		condition = ("WHERE id=%d" % game_id) if game_id else ""
		game = DB.getOne("""
			SELECT
				*,
				(SELECT count(*) FROM word WHERE game_id = game.id) words
			FROM game %s ORDER BY createDate DESC
		""" % condition)
		if not game:
			return None
		game['rounds'] = Round.getByGame(game['id'])
		game['roundsCount'] = len(game['rounds'])
		game['roundsNumber'] = ", ".join([str(r['number']) for r in game['rounds']])
		game['lastRoundNumber'] = game['rounds'][-1]['number']
		game['lastRoundCreateDate'] = game['rounds'][-1]['createDate']
		game['lastRoundWords'] = game['rounds'][-1]['words']
		game['lastRoundPlayers'] = game['rounds'][-1]['players']
		game['lastRoundPlayersPlain'] = "\n".join(["%s: %s" % (p, str(w)) for p, w in game['lastRoundPlayers'].items()]) if game['lastRoundPlayers'] else ""
		return game

	@staticmethod
	def getPlayerWordsByRound(update, round_id=None, fullAccess=False):
		player_id = Player.getId(update.message.chat)
		if not round_id:
			game_id, round_id = Base_Game._getId(doNotInitNewGame=True)
		return Word.getListByRoundId(round_id, player_id, fullAccess)

	@staticmethod
	def getPlayerWordsByGame(update, game_id=None, fullAccess=False):
		player_id = Player.getId(update.message.chat)
		game_id, round_id = Base_Game._getId(game_id)
		return Word.getListByGameId(game_id, player_id, fullAccess)

	def getRandom(self, dictionaryName, minLength=5):
		attemptsLimit = 10
		attempt = 1
		while attempt <= attemptsLimit:
			attempt += 1
			word = random.choice(list(open(self._DICTIONARIES[dictionaryName])))
			if Word.isWordValid(word, minLength)[0]:
				return word
		return None

	def getCandidates(self):
		self._refreshGameState()
		wordsListByAuthor = Word.getListByRoundId(self.round_id, fullAccess=True)
		print(wordsListByAuthor)

	@staticmethod
	def _init():
		game_id = DB.execute("INSERT INTO game SET createDate = NOW()").lastrowid
		logging.info("New game was started. ID: %d" % game_id)
		return game_id

	@staticmethod
	def _getId(game_id=None, doNotInitNewGame=False):
		condition = "DATE(createDate) = DATE(NOW())" if not game_id else "id = %d" % game_id
		game = DB.getOne("SELECT * FROM game WHERE winner_id IS NULL AND %s" % condition)
		if doNotInitNewGame and not game:
			return None
		game_id = Base_Game._init() if not game else game['id']
		return game_id, Round.getId(game_id)

	def start(self):
		raise NotImplementedError("Method must be override")

