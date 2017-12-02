from libs.dbAdapter import DB
import re
import logging
from game.player import Player
from game.word import Word
from game.round import Round


class Base_Game:

	ERROR_CODES = {
		"INNER_ERROR": "Ебануться! Что-то пошло не так. Я не смог сохранить твоё словцо. Не делай так больше!",
		"EMPTY_WORD": "Словцо-то введи, горемыка.",
		"TOO_MANY_WORDS": "Ты что мне суешь, пёс! Сишком много словцов за раз. Можно только %d!",
	}

	_WORDS_LIMIT = 1
	_WORD_MIN_LENGTH = 5

	def addWord(self, update):
		errorMsg = None
		wordsList = re.sub("\s{2,}", " ", update.message.text).strip().split(" ")
		if not wordsList:
			errorMsg = Base_Game.ERROR_CODES['EMPTY_WORD']
		if len(wordsList) > Base_Game._WORDS_LIMIT:
			errorMsg = Base_Game.ERROR_CODES['TOO_MANY_WORDS'] % self._WORDS_LIMIT
		if errorMsg:
			return errorMsg
		successMsg = ""
		game_id, round_id = self._getId()
		player_id = Player.getId(update.message.chat.first_name)
		for word in wordsList:
			params = dict(word=word.lower(), player_id=player_id, game_id=game_id, round_id=round_id)
			wordStatus = Word.add(params, self._WORDS_LIMIT, self._WORD_MIN_LENGTH)
			successMsg += "%s\n" % wordStatus[1]
		return successMsg.strip()

	def updateWord(self, oldWord, newWord, update):
		game_id, round_id = Base_Game._getId()
		player_id = Player.getId(update.message.chat.first_name)
		return Word.update(oldWord=oldWord, newWord=newWord, player_id=player_id, round_id=round_id, wordMinLength=self._WORD_MIN_LENGTH)

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
		return game

	@staticmethod
	def getPlayerWordsByRound(round_id=None, playerName=None, fullAccess=False):
		player_id = Player.getId(playerName)
		if not round_id:
			game_id, round_id = Base_Game._getId(doNotInitNewGame=True)
		return Word.getListByRoundId(round_id, player_id, fullAccess)

	@staticmethod
	def getPlayerWordsByGame(game_id=None, playerName=None, fullAccess=False):
		player_id = Player.getId(playerName)
		game_id, round_id = Base_Game._getId(game_id)
		return Word.getListByGameId(game_id, player_id, fullAccess)

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

	@staticmethod
	def _start():
		raise NotImplementedError("Method must be override")

