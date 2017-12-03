from libs.dbAdapter import DB
import logging
import random
from collections import OrderedDict
from libs.coll import splitList, simpleDictMerge
from game.player import Player
from game.word import Word
from game.round import Round
from game.group import Group


class Base_Game:

	ERROR_CODES = {
		"INNER_ERROR": "Ебануться! Что-то пошло не так. Я не смог сохранить твоё словцо. Не делай так больше!"
	}

	_ROUNDS = dict()

	_DICTIONARIES = {
		"ushakov": r"f:\WordsJugglerBot\dictionaries\ushakov_reb.txt"
	}

	_RANDOM_PLAYER = {'id': -1, 'first_name': "Жорж"}

	game_id = None
	round_id = None
	roundNumber = None

	def _refreshGameState(self):
		self.game_id, self.round_id = self._getId()
		_round = Round.get(self.round_id)
		self.roundNumber = _round['number']
		self.roundStatus = _round['status']
		self.gameState = dict(game_id=self.game_id, round_id=self.round_id, roundNumber=self.roundNumber, roundStatus=self.roundStatus)
		self.roundSettings = self._ROUNDS[self.roundNumber]

	def addWord(self, update):
		self._refreshGameState()
		if self.roundStatus != Round.STATUS_PREPARATION:
			return "Слишком поздно вертеть задом. Раунд уже началася. Дождись окончания раунда"
		return Word.add(dict(
			word=update.message.text,
			player_id=Player.getId(update.message.chat),
			game_id=self.game_id,
			round_id=self.round_id),
			self.roundSettings['minWordsPerPlayer'],
			self.roundSettings['minWordLength']
		)[1]

	def updateWord(self, oldWord, newWord, update):
		self._refreshGameState()
		player_id = Player.getId(update.message.chat)
		if Player.getState(player_id=player_id, **self.gameState):
			return "Ты не можешь обновить своё убогое словцо, если ты уже приготовился играть, вонючка!"
		return Word.update(oldWord=oldWord, newWord=newWord, player_id=player_id, round_id=self.round_id, wordMinLength=self.roundSettings['minWordLength'])

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

	def setPlayerState(self, update):
		self._refreshGameState()
		if self.roundStatus != Round.STATUS_PREPARATION:
			return "Поздняк метаться. Раунд уже запущен. Молись!"
		player_id = Player.getId(update.message.chat)
		playerWords = Word.getListByRoundId(round_id=self.round_id, player_id=player_id)
		if len(playerWords) < self.roundSettings['minWordsPerPlayer']:
			return "Надо предложить побольше словцов, чтобы быть готовым. Осталось предложить: %d/%d" % (len(playerWords), self.roundSettings['minWordsPerPlayer'])
		return "Ты больше не готов к игре в этом раунде, трусиха" if not Player.setState(player_id=player_id, round_id=self.round_id) else \
			"Ты изготовился к игре. Удач!"

	def getCandidates(self, update):
		self._refreshGameState()
		fullInfoWordsList = Word.getListByRoundId(self.round_id, fullAccess=True)
		wordsByPlayer = dict()
		for wordInfo in fullInfoWordsList:
			if wordInfo['player_id'] not in wordsByPlayer:
				wordsByPlayer[wordInfo['player_id']] = dict(
					words=[],
					isReady=Player.getState(player_id=wordInfo['player_id'], round_id=self.round_id),
					name=wordInfo['name'],
					telegram_id=wordInfo['telegram_id'],
					player_id=wordInfo['player_id'],
				)
			wordsByPlayer[wordInfo['player_id']]['words'].append((wordInfo['id'], wordInfo['word']))
		unreadyPlayers = [p['name'] for p in wordsByPlayer.values() if not p['isReady'] and p['telegram_id'] != self._RANDOM_PLAYER['id']]
		if len(wordsByPlayer) < self.roundSettings['minPlayer']:
			return "Что-то маловато народца набралось для игры (%d/%d). Зови друзей" % (len(wordsByPlayer), self.roundSettings['minPlayer'])
		if 'maxPlayer' in self.roundSettings and len(wordsByPlayer) > self.roundSettings['maxPlayer']:
			return "Ого сколько вас набежало. Слишком много вас, а я один (%d/%d). Пошли вон!" % (len(wordsByPlayer), self.roundSettings['maxPlayer'])
		if unreadyPlayers:
			return "Слишком много тормозов в игре. Я не могу показать тебе словцы, пока все не будут готовы. Список тормозов:\n%s" % " ".join(unreadyPlayers)
		if self.roundStatus == Round.STATUS_PREPARATION:
			Round.updateRoundStatus(round_id=self.round_id, status=Round.STATUS_IN_PROGRESS)
		self._addRandomWord()
		wordsList = self._splitWordsIntoGroups([word for wordsInfo in wordsByPlayer.values() for word in wordsInfo['words']])
		return """
			Вот список всех словцов. Кроме того я добавил в него несколько случайных (а может и нет). Хехе.
			Добавь в них вместо ноликов свои баллы.
			<b>%s</b>
			Суммарное максимальное количество баллов: %d
			Суммарное минимальное количество баллов: %d
			Максимальное количество баллов на слово: %d
		""" % (
			"\n".join(["Группа %d: %s" % (i, " 0 ".join(w)) for i, w in wordsList.items()]),
			self.roundSettings['maxWeightPerRound'],
			self.roundSettings['minWeightPerRound'],
			self.roundSettings['maxWeightPerWord']
		)

	def _splitWordsIntoGroups(self, words, expelSuperfluousWords=True):
		self._refreshGameState()
		savedGroups = Group.getGroups(self.gameState)
		if savedGroups:
			return savedGroups
		random.shuffle(words)
		groupSize = len(words) if self.roundSettings['groupSize'] == -1 else self.roundSettings['groupSize']
		groups = OrderedDict((i+1, v) for i, v in enumerate(splitList(words, groupSize)))
		for groupNumber, wordsList in groups.items():
			status = Group.STATUS_EXILE if expelSuperfluousWords and len(wordsList) < self.roundSettings['groupSize'] else Group.STATUS_UNDEFINED
			for wordInfo in wordsList:
				Group.addWordToGroup(
					simpleDictMerge(
						dict(word_id=wordInfo[0], number=groupNumber, status=status),
						self.gameState,
					)
				)
		return OrderedDict((i, [w[1] for w in words]) for i, words in groups.items())

	# def _saveWordIntoGr

	def _addRandomWord(self):
		if 'randomWordsLimit' not in self.roundSettings:
			return
		self._refreshGameState()
		randomWordsCount = 0
		wordsAdded = 0
		while wordsAdded < self.roundSettings['randomWordsLimit']:
			if randomWordsCount > 20:
				break
			randomWordsCount += 1
			word = self.getRandom("ushakov")
			if not word:
				continue
			Word.add(dict(
				word=word,
				player_id=Player.getId(self._RANDOM_PLAYER),
				game_id=self.game_id,
				round_id=self.round_id),
				self.roundSettings['minWordsPerPlayer'],
				self.roundSettings['minWordLength']
			)
			wordsAdded += 1

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

