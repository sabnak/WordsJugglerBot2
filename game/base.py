from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from libs.dbAdapter import DB
import random
from collections import OrderedDict
from libs.coll import bestOfMultipleSmart, md5, Config, buildMenu
import re
from libs.coll import splitList
from game.player import Player
from game.word import Word
from game.round import Round
from game.group import Group
from game.vote import Vote
from game.log import Log
from game.game import Game
from game.series import Series
import json
import logging


class Base_Game:

	_SETTINGS = dict()

	_DICTIONARIES = {
		"ushakov": r"./dictionaries/ushakov_reb.txt"
	}

	_RANDOM_PLAYER = {
		'id': -1,
		'first_name': "Жорж"
	}

	_GENERATED_GAME_HARD_WORDS_LIMIT = 100
	_MAX_OPENED_GAMES_PER_PLAYER = 5
	PASSWORD_MIN_LENGTH = 3
	PASSWORD_NO_PASSWORD_MARK = "без пароля"

	STATUS_PREPARATION = "preparation"
	STATUS_IN_PROGRESS = "in progress"
	STATUS_ENDED = "ended"
	STATUS_ABORTED = "aborted"

	_gameState = None
	_seriesState = None
	_playerState = None

	def __init__(self, update):
		self.update = update
		self._refreshPlayerState()
		self.game = Game()

	def _refreshPlayerState(self, newPlayer=False):
		telegram_id = self.update.effective_user.id
		logging.info("Refreshing player telegram_id %s" % str(telegram_id))
		if self._playerState and not telegram_id:
			telegram_id = self._playerState['telegram_id']
		self._playerState = Player.get(telegram_id=telegram_id)
		if not self._playerState:
			if newPlayer:
				raise PlayerAddingError
			Player.add(self.update)
			self._refreshPlayerState(True)

	def _refreshGameState(self,	checkGameStatus=True):
		"""
		Updates game state (game_id, round_id etc.)
		Must be calls in every public method
		"""
		logging.info("Refreshing game state for player ID %d" % self._playerState['id'])

		self._refreshSeriesState()

		self._gameState = self.joinGame()[0]

		if not self._gameState:
			raise GameWasNotFoundError

		self._gameState['game_id'] = self._gameState['id']

		self._gameState['round'] = Round.getLast(game_id=self._gameState['game_id'])
		self._gameState['roundStatus'] = self._gameState['round']['status']
		self._gameState['roundNumber'] = self._gameState['round']['number']
		self._gameState['round_id'] = self._gameState['round']['id']

		self._gameSettings = {int(r): s for r, s in self._gameState['settings']['round'].items()}
		self._roundSettings = self._gameSettings[self._gameState['round']['number']]

		del self._gameState['settings']

		self._gameState['query'] = dict(
			game_id=self._gameState['game_id'],
			round_id=self._gameState['round_id'],
			roundStatus=self._gameState['roundStatus'],
			roundNumber=self._gameState['roundNumber'],
			series_id=self._gameState['series_id']
		)

		if checkGameStatus:
			self._isGameReady()

	def _refreshSeriesState(self, password=None):

		logging.info("Refreshing series state for player ID %d" % self._playerState['id'])
		self._refreshPlayerState()
		self._seriesState = Series.get(series_id=self._playerState['series_id'])

		if not self._seriesState:
			raise SeriesWasNotFoundError

		if not self._isPlayerHasAccessToSeries(self._seriesState['id'], password):
			raise SeriesAccessDeniedError

	def createGame(self):
		self._refreshSeriesState()
		return self._createGame(activeGames=self._seriesState['settings']['maxOpenedGamesOverall'])

	def _createGame(self, status=Game.STATUS_PREPARATION, role=Game.PLAYER_ROLE_ADMIN, activeGames=1):
		self._refreshSeriesState()

		logging.info("Trying to create new game")

		createdGames = self.game.getList(
			series_id=self._seriesState['id'],
			status=[Base_Game.STATUS_PREPARATION, Base_Game.STATUS_IN_PROGRESS]
		)

		if createdGames and len(createdGames) >= activeGames:
			logging.info("Too many player active games")
			return """
				Слишком много активных игр в серии.
				Максимум активных игр: %d
			""" % self._seriesState['settings']['maxOpenedGamesOverall']

		createdGamesByPlayer = self.game.getList(
			creator_id=self._playerState['id'],
			series_id=self._playerState['series_id'],
			status=[Base_Game.STATUS_PREPARATION, Base_Game.STATUS_IN_PROGRESS]
		)

		if createdGamesByPlayer and len(createdGamesByPlayer) >= self._seriesState['settings']['maxOpenedGamesPerPlayer']:
			logging.info("Too many active games")
			return """
				Тобой создано слишком много активных игр в серии.
				Заверши предыдущие, чтобы создавать новые.
				Максимум активных игр на игрока: %d
			""" % self._seriesState['settings']['maxOpenedGamesPerPlayer']

		game = self.game.create(
			player_id=self._playerState['id'],
			series_id=self._seriesState['id'],
			settings=json.dumps(self._seriesState['settings']['game'] if 'game' in self._seriesState['settings'] else self._SETTINGS),
			status=status,
			gameRole=role
		)

		response = """
			Игра <b>%d</b> успешно создана
			Для просмотра настроек испрльзуй "/gamesettings"
			Для задания пароля используй "/gameset password ПАРОЛЬ"
			Для изменения других настроек используй\n "/gameset НОМЕР_РАУНДА ПАРАМЕТР ЗНАЧЕНИЕ"
			Для запуска игры используй "/gamestart"
		""" % game['id']

		logging.info("Game ID %d created successfully" % game['id'])

		return response

	def startGame(self):
		# TODO: Дробавить проверку на владельца игры
		self._refreshGameState(checkGameStatus=False)
		if self._gameState['status'] == Game.STATUS_IN_PROGRESS:
			return "Зачем?.. Игра уже начата. Чего ж тебе ещё надо-то?"
		if self._gameState['status'] == Game.STATUS_ENDED:
			return "Игра закончена. Смирись"
		if self._playerState['game_id'] == self._gameState['game_id'] and self._playerState['game_role'] == Game.PLAYER_ROLE_ADMIN:
			Game.setGameStatus(game_id=self._gameState['game_id'], status=Game.STATUS_IN_PROGRESS)
			return "Ииииигра началась! Теперь людишки могут к ней присоединяться"
		return "Не могу начать игру. Может у тебя недостаточно прав? Игру могут начинать только админы"

	def setGameSettings(self, roundNumber, name, value, addButtons=True):
		self._refreshGameState(checkGameStatus=False)

		if self._gameState['creator_id'] != self._playerState['id']:
			return "Э! Куда лезешь! Только создатель игры может изменить её настройки."

		if roundNumber not in self._gameSettings:
			return "Кажется, в игре нет настроек для раунда <b>№%d</b>. Ты точно всё делаешь правильно, дорогуша?" % roundNumber

		if name not in self._gameSettings[roundNumber]:
			return "Ой-вэй, куда ты тычешь? В раунде <b>№%d</b> нет настройки для <b>%s</b>." % (roundNumber, name)

		currentValue = self._gameSettings[roundNumber][name]

		try:
			self._gameSettings[roundNumber][name] = type(currentValue)(value)
		except TypeError:
			return """
				Плохое значение зачем передал для <b>%s</b>, а?
				<b>%s</b> совсем не подходит.
				Попробуй передать что-то похожее на тип <b>%s</b>
			""" % (name, value, type(currentValue).__name__)

		self._gameState['settings'] = json.dumps(dict(round=self._gameSettings))

		self.game.updateSettings(**self._gameState)

		if addButtons:
			buttonList = self._buildSettingsButton(roundNumber, name, self._gameSettings[roundNumber][name])
			return buttonList

		return "Я очень успешно установил настройку <b>%s</b> = <b>%s</b> для раунда <b>№%d</b>" % (name, str(value), roundNumber)

	def getGameSettingsButtons(self):

		self._refreshGameState(checkGameStatus=False)

		if self._gameState['creator_id'] != self._playerState['id']:
			return "Э! Куда лезешь! Только создатель игры может изменить её настройки."

		response = []

		for roundNumber, settings in self._gameSettings.items():
			response.append("Раунд <b>%d</b>" % roundNumber)
			for optionName, optionValue in settings.items():
				buttonList = self._buildSettingsButton(roundNumber, optionName, optionValue)
				if not buttonList:
					continue
				response.append(buttonList)
		return response

	def getGameSettings(self):
		self._refreshGameState(checkGameStatus=False)

		response = [
			"Серия ID %d. Игра ID %d" % (self._seriesState['id'], self._gameState['game_id']),
			"Дата создания: %s" % self._gameState['createDate'].strftime('%Y-%m-%d %H:%M:%S'),
			"Статус: %s" % self._gameState['status'],
			"Пароль: %s " % ("да" if self._gameState['password'] else "нет"),
			"<pre> </pre>",
			"Настройки:",
			"\n ".join(
				[
					"<b>Раунд №%s</b>\n%s" % (
						number,
						"\n ".join(
							[
								"%s: %s" % (
									name,
									value
								) for name, value in settings.items()
							]
						)
					) for number, settings in self._gameSettings.items()
				]
			),
		]

		if self._gameState['creator_id'] != self._playerState['id']:
			response += [
				"Для задания пароля используй \"/gameset password ПАРОЛЬ\"",
				"Для изменения других настроек используй\n \"/gameset НОМЕР_РАУНДА ПАРАМЕТР ЗНАЧЕНИЕ\"",
				"Для запуска игры используй \"/gamestart\"",
			]

		return response

	@staticmethod
	def _buildSettingsButton(roundNumber, name, value):
		if not isinstance(value, (float, int)):
			return None
		newOptionValueInc = value + 1
		newOptionValueDec = value - 1
		buttonList = [
			InlineKeyboardButton(" +1 ", callback_data="%d %s %d" % (roundNumber, name, newOptionValueInc)),
			InlineKeyboardButton(" -1 ", callback_data="%d %s %d" % (roundNumber, name, newOptionValueDec)),
		]
		return dict(
			msg="%s %s" % (name, value),
			buttons=InlineKeyboardMarkup(buildMenu(buttonList, nCols=2))
		)

	def setGamePassword(self, password):
		self._refreshGameState()
		password = self._generatePassword(password)
		if self._playerState['game_id'] == self._gameState['game_id'] and self._playerState['game_role'] == Game.PLAYER_ROLE_ADMIN:
			Game.setGamePassword(game_id=self._gameState['game_id'], password=password)
			return "Пароль успешно обновлён. Скорее расскажи его всем!"
		return "Хе-хе. Похоже, у тебя не хватает прав для задания пароля для игры!"

	def joinGame(self, game_id=None, password=None):
		if password:
			password = self._generatePassword(password)
		self._refreshSeriesState()
		if not game_id:
			game = Game.getPlayerLastGame(series_id=self._seriesState['id'], player_id=self._playerState['id'])
			if not game or game['status'] == Base_Game.STATUS_ENDED:
				game = Game.getLastGameInSeries(series_id=self._seriesState['id'])
				if not game:
					raise GameWasNotCreateError
		else:
			game = Game.get(game_id=game_id)
			if not game:
				raise GameWasNotCreateError

		self._isPlayerHasAccessToGame(game['id'], password)

		if self._playerState['game_id'] != game['id']:
			Player.joinGame(
				player_id=self._playerState['id'],
				role=Game.PLAYER_ROLE_MEMBER,
				game_id=game['id']
			)

			if password:
				Player.setGamePassword(
					player_id=self._playerState['id'],
					game_id=game['id'],
					password=password
				)

		# self._refreshGameState(password=password, game_id=game['id'], checkGameStatus=False)

		return game, "Иииха! Ты присовокупился к игре с ID %d серии игр с ID %d" % (game['id'], self._seriesState['id'])

	def joinSeries(self, series_id, password=None):
		if password:
			password = self._generatePassword(password)
		# TODO: Обнулять game_id при присоединении к серии
		series = Series.get(series_id=series_id)
		if not series:
			return "Иисусе, да нет серии игры с таким ID!"

		if not self._isPlayerHasAccessToSeries(series['id'], password):
			raise SeriesAccessDeniedError

		Player.joinSeries(
			player_id=self._playerState['id'],
			role=Series.PLAYER_ROLE_MEMBER,
			series_id=series_id
		)

		if password:
			Player.setSeriesPassword(
				player_id=self._playerState['id'],
				series_id=series_id,
				password=password
			)

		self._refreshSeriesState(password=password)

		return "Класс. Ты присоединился к серии игр \"%s\" с ID %d" % (series['name'], series_id)

	def _isPlayerHasAccessToSeries(self, series_id, password=None):
		series = Series.get(series_id=series_id)
		if not series_id:
			return False
		if not series['password']:
			return True

		storedPlayerPassword = Player.getSeriesPassword(player_id=self._playerState['id'], series_id=series_id)

		if series['password'] == storedPlayerPassword:
			return True

		if series['password'] == password:
			return True

		return False

	def _isGameReady(self):

		if self._gameState['status'] == Game.STATUS_ENDED:
			raise GameWasNotCreateError

		if self._gameState['status'] == Game.STATUS_PREPARATION:
			raise GameWasNotStartError

		return True if self._gameState['status'] == Base_Game.STATUS_IN_PROGRESS else False

	def _isPlayerHasAccessToGame(self, game_id, password=None):
		game = Game.get(game_id=game_id)
		if not game_id:
			raise GameAccessDeniedError

		if game['status'] == Base_Game.STATUS_PREPARATION and self._playerState['id'] != game['creator_id']:
			raise GameWasNotStartError

		if not game['password']:
			return True

		storedGamePassword = Player.getGamePassword(player_id=self._playerState['id'], game_id=game_id)

		if game['password'] == storedGamePassword:
			return True

		if game['password'] == password:
			return True

		raise GameAccessDeniedError

	@staticmethod
	def getSeriesList():
		seriesList = Series.getList()
		if not seriesList:
			return "Нет ни одной активной серии игр. Да быть такого не может!"
		responseList = []
		for series in seriesList:
			responseList.append("<b>%s</b>: %s" % (series['id'], series['name']))
		return "\n".join(responseList)

	def getPlayerStatus(self):
		self._refreshGameState(checkGameStatus=False)
		responseList = [
			"Текущая серия: \"%s\". ID: %d" % (self._seriesState['name'], self._seriesState['id']),
			"Текущая игра, ID: %s" % (str(self._gameState['game_id']) if self._gameState else "не начата")
		]
		return "\n".join(responseList)

	def addWord(self, update):
		"""
		Adds word into current round of the game
		:param update: dict with update info
		:return: str text response
		"""
		self._refreshGameState(checkGameStatus=True)

		if self._gameState['roundStatus'] != Round.STATUS_PREPARATION:
			return "Слишком поздно вертеть задом. Раунд уже началася. Дождись окончания раунда"

		return Word.add(
			word=update.message.text,
			player_id=self._playerState['id'],
			wordsLimit=self._roundSettings['minWordsPerPlayer'],
			wordMinLength=self._roundSettings['minWordLength'],
			**self._gameState['query']
		)[1]

	def start(self):
		"""
		Starts new game
		:return: str text response
		"""
		self._refreshGameState(checkGameStatus=True)

		groups = Group.get(groupByGroupNumber=True, **self._gameState['query'])
		if self._gameState['roundStatus'] != Round.STATUS_IN_PROGRESS:
			return "Не надо огня! Рано ещё начинать рубку. Предлагайте свои словцы и голосуйте за другие"

		lazyPlayers = dict()
		cheaters = dict()
		responseList = []
		preparedGroups = OrderedDict()
		wordsByWord = dict()
		statsByPlayer = dict()

		for groupNumber, group in groups.items():
			wordsList = []
			weightsList = dict()

			for info in group:
				if info['player_id'] not in statsByPlayer:
					statsByPlayer[info['player_id']] = dict(words={}, name=info['name'])
				if info['word'] not in statsByPlayer[info['player_id']]['words']:
					statsByPlayer[info['player_id']]['words'][info['word']] = dict()
				if info['electorPlayer_id']:
					statsByPlayer[info['player_id']]['words'][info['word']][info['electorPlayer_id']] = dict(name=info['electorName'], weight=info['weight'])
				if info['telegram_id'] != self._RANDOM_PLAYER['id']:
					playerSpentWeight = Vote.getPlayerSumOfWeightPerRound(player_id=info['player_id'], **self._gameState['query'])
					if playerSpentWeight < self._roundSettings['maxWeightPerRound']:
						lazyPlayers[info['player_id']] = dict(name=info['name'], spentWeight=playerSpentWeight)
					if playerSpentWeight > self._roundSettings['maxWeightPerRound']:
						cheaters[info['player_id']] = dict(name=info['name'], spentWeight=playerSpentWeight)
				if info['word'] not in wordsByWord:
					wordsByWord[info['word']] = info
				if info['word'] not in wordsList:
					wordsList.append(info['word'])

				if not info['weight']:
					electorPlayer_id = -2 if not info['electorPlayer_id'] else info['electorPlayer_id']
					weight = 0
				else:
					electorPlayer_id = info['electorPlayer_id']
					weight = info['weight']
				if electorPlayer_id not in weightsList:
					weightsList[electorPlayer_id] = []
				weightsList[electorPlayer_id].append((info['word'], weight))
			preparedGroups[groupNumber] = dict(words=wordsList, weights=weightsList)

		if lazyPlayers or cheaters:
			responseList.append("Ничего у нас не выйдет!")
			if lazyPlayers:
				responseList.append("Эти ленивые задницы до сих пор не вложили все свои баллы:\n%s" % " ".join("%s (%d)" % (x['name'], x['spentWeight']) for x in lazyPlayers.values()))
			if cheaters:
				responseList.append("А этим засранцам как-то удалось вложить больше баллов:\n%s" % " ".join("%s (%d)" % (x['name'], x['spentWeight']) for x in lazyPlayers.values()))
			return "\n".join(responseList)
		responseList = [
			"Игра от <b>%(createDate)s</b>. Раунд <b>%(roundNumber)d</b>" % self._gameState
		]
		winners = []

		for groupNumber, group in preparedGroups.items():
			winnerWord, stats = self._start(group['words'], group['weights'])
			stats['players'] = statsByPlayer
			winners.append(
				dict(
					player_id=wordsByWord[winnerWord]['player_id'],
					word_id=wordsByWord[winnerWord]['word_id']
				)
			)
			responseList += self._getPrettyGroupResultsList(stats, winnerWord, groupNumber, **self._gameState['query'])
			Log.save(
				data=json.dumps(stats),
				group_id=wordsByWord[winnerWord]['group_id'],
				winnerPlayer_id=wordsByWord[winnerWord]['player_id'],
				winnerWord_id=wordsByWord[winnerWord]['word_id'],
				**self._gameState['query']
			)

		Round.updateRoundStatus(status=Round.STATUS_ENDED, **self._gameState['query'])
		if self._gameState['roundNumber'] + 1 not in self._roundSettings:
			self.game.update(
				status=Base_Game.STATUS_ENDED,
				winner_id=winners[0]['player_id'] if len(winners) == 1 else None,
				winnerWord_id=winners[0]['word_id'] if len(winners) == 1 else None,
				**self._gameState['query']
			)

		return "\n".join(responseList)

	@staticmethod
	def _getPrettyGameResults(gamesLog):
		"""
		Format game result into pretty text view
		:param gamesLog: dict of game log
		:return: str with text response
		"""
		responseList = []

		for game_id, gameInfo in gamesLog.items():
			responseList.append("Лог игры ID <b>%d</b> от %s" % (game_id, gameInfo['createDate']))
			for round_id, roundInfo in gameInfo['rounds'].items():
				responseList.append("Раунд № <b>%d</b>" % roundInfo['number'])
				for group_id, groupInfo in roundInfo['groups'].items():
					responseList += Base_Game._getPrettyGroupResultsList(
						stats=groupInfo['data'],
						winnerWord=groupInfo['winnerWord'],
						groupNumber=groupInfo['number'],
						game_id=game_id,
						round_id=round_id
					)

		return "\n".join(responseList)

	@staticmethod
	def _getPrettyGroupResultsList(stats, winnerWord, groupNumber=None, isGeneratedGame=False, **gameState):
		"""
		Format group results into pretty text viw
		:param stats: dict of group log
		:param winnerWord:
		:param groupNumber:
		:param gameState:
		:return: str with text response
		"""
		if isGeneratedGame:
			responseList = [
				"<b>Баллы:</b>\n%s" % "\n".join(["%d: %s" % (p, w) for w, p in stats['points'].items()]),
			]
		else:
			responseList = [
				"<b>Группа %d</b>" % groupNumber
			]

		responseList += [
			"<b>Вероятности:</b>\n%s" % "\n".join(["%.2f: %s" % (p[1], w) for w, p in stats['weights'].items()]),
			"<b>Слово-победитель:</b> <b>%s</b>" % winnerWord
		]

		if not isGeneratedGame:
			responseList += [
				"<b>Игрок-победитель: %s</b>" % Player.getPlayerByWord(word=winnerWord, **gameState)['name'],
				"<b>Участники:</b>",
			]

		if isGeneratedGame and 'debug' in stats:
			responseList.append("<b>Дебаг</b>")
			responseList += ["<b>%s:</b>\n\n%s\n%s" % (name, info['description'], str(info['value'])) for name, info in stats['debug'].items()]

		if isGeneratedGame:
			return responseList

		for playerInfo in stats['players'].values():
			responseList.append("<b>%s</b>" % playerInfo['name'])
			for word, wordInfo in playerInfo['words'].items():
				responseList.append("* %s (%d)" % (word, sum([e['weight'] for e in wordInfo.values()])))
				for elector in wordInfo.values():
					responseList.append("++ %s: %d" % (elector['name'], elector['weight']))

		return responseList

	def updateWord(self, update, oldWord, newWord):
		"""
		Update player word
		:param update: dict with update info
		:param oldWord:
		:param newWord:
		:return: str with text response
		"""
		self._refreshGameState(checkGameStatus=True)
		player_id = Player.getId(update.message.chat)
		if self._gameState['roundStatus'] == Round.STATUS_IN_PROGRESS:
			return "Ахаха. Раунд-то уже начался. Поздно теперь крутить себе соски. Надейся на лучшее!"
		if Player.getState(player_id=player_id, **self._gameState['query']):
			return "Ты не можешь обновить своё убогое словцо, если ты уже приготовился играть, вонючка!"
		return Word.update(
			oldWord=oldWord,
			newWord=newWord,
			player_id=player_id,
			wordMinLength=self._roundSettings['minWordLength'],
			**self._gameState['query']
		)

	@staticmethod
	def get(game_id=None):
		"""
		Returns game summary
		:param game_id:
		:return: dict with game stats
		"""
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

	def getList(self, limit=None):
		self._refreshSeriesState()
		if not limit:
			limit = 100
		gamesList = DB.getList("""
			SELECT 
				game.id, 
				game.createDate, 
				game.status, 
				p1.name winner_name,
				p2.name creator_name,
				word
			FROM game
			LEFT JOIN player p1 ON (p1.id=game.winner_id)
			JOIN player p2 ON (p2.id=game.creator_id)
			LEFT JOIN word ON (word.id=game.winner_id)
			WHERE game.series_id = %d
			ORDER BY createDate DESC
			LIMIT %d
		""" % (self._seriesState['id'], limit))
		if not gamesList:
			return "Возмутительно! До сих пор не было сыграно ни одной игры!"
		responseList = ["Список последних %d игр" % limit]
		for game in gamesList:
			responseList.append("Игра ID <b>%d</b> от %s. Статус: <b>%s</b>" % (
				game['id'],
				game['createDate'].strftime('%Y-%m-%d %H:%M:%S'),
				game['status']
			))
			responseList.append("Автор: <b>%s</b>" % game['creator_name'])
			responseList.append("Победитель: <b>%s (%s)</b>" % (game['winner_name'], game['word']))
			responseList.append("<pre></pre>")
		return "\n".join(responseList)

	def getLastGameLog(self, status=STATUS_ENDED):
		lastGame = Game.getLastGameInSeries(series_id=self._playerState['series_id'], status=Game.STATUS_ENDED)
		if not lastGame:
			return "Не получается найти лог последней игры.\nВозможно, игра ещё не была завершена?"
		return Base_Game.getGameLog(game_id=lastGame['id'])

	@staticmethod
	def getGameLog(game_id):
		log = Base_Game._getGameLog(game_id=game_id)
		if not log:
			return "Не получается найти лог игры с ID <b>%d</b>." % game_id
		return Base_Game._getPrettyGameResults(log)

	@staticmethod
	def _getGameLog(**params):
		game = Game.getFullInfo(**params)
		if not game:
			return None
		return Log.get(game_id=game['id'])

	def getPlayerWordsByRound(self, round_id=None, fullAccess=False):
		"""
		:param round_id: int
		:param fullAccess: bool if True access to to all words otherwise your own
		:return: list of founded words
		"""
		self._refreshGameState()

		o = dict(
			game_id=self._gameState['query']['game_id'],
			player_id=self._playerState['id'],
			fullAccess=fullAccess,
			round_id=round_id if round_id else self._gameState['query']['round_id']
		)

		return Word.getListByRoundId(**o)

	def getPlayerWordsByGame(self, fullAccess=False):
		self._refreshGameState(checkGameStatus=True)
		return Word.getListByGameId(player_id=self._playerState['id'], fullAccess=fullAccess, **self._gameState['query'])

	def getRandom(self, dictionaryName, wordMinLength=5):
		return self._getRandom(dictionaryName=dictionaryName, wordMinLength=wordMinLength, checkExistence=False)

	def _getRandom(self, dictionaryName, wordMinLength=5, checkExistence=True):
		attemptsLimit = 10
		attempt = 1
		params = dict(wordMinLength=wordMinLength)
		if checkExistence:
			params['series_id'] = self._seriesState['id']
			params['checkExistence'] = True
		else:
			params['series_id'] = None
			params['checkExistence'] = False
		while attempt <= attemptsLimit:
			attempt += 1
			word = random.choice(list(open(self._DICTIONARIES[dictionaryName], encoding="utf-8")))
			if Word.isWordValid(word=word, **params)[0]:
				return word
		return None

	# TODO: Сделать статичным
	def generate(self, wordsLimit, weightsList, params=None):
		self._refreshGameState(checkGameStatus=False)
		wordsCount = 0
		wordsList = []
		weightsListParsed = dict()
		if wordsLimit > self._GENERATED_GAME_HARD_WORDS_LIMIT:
			return "Слишком много словцов для генерации. Пожалуй. Максимум в игре могут участвовать %d словцов" % self._GENERATED_GAME_HARD_WORDS_LIMIT
		if not params:
			params = {}
		while wordsCount < wordsLimit:
			randomWord = self._getRandom("ushakov")
			if not randomWord:
				return "Не могу добавить случайное словцо. Паникуй!"
			wordsList.append(randomWord)
			weightsListParsed[wordsCount] = [(randomWord, weightsList[wordsCount] if len(weightsList) >= wordsCount + 1 else 0)]
			wordsCount += 1
		winnerWord, stats = bestOfMultipleSmart(wordsList, weightsListParsed, **params)
		responseList = self._getPrettyGroupResultsList(stats, winnerWord, isGeneratedGame=True, **self._gameState['query'])
		return "\n".join(responseList)

	def setPlayerState(self, update):
		self._refreshGameState(checkGameStatus=True)
		if self._gameState['roundStatus'] != Round.STATUS_PREPARATION:
			return "Поздняк метаться. Раунд уже запущен. Молись!"
		player_id = Player.getId(update.message.chat)
		playerWords = Word.getListByRoundId(player_id=player_id, **self._gameState['query'])
		if len(playerWords) < self._roundSettings['minWordsPerPlayer']:
			return "Надо предложить побольше словцов, чтобы быть готовым. Осталось предложить: %d/%d" % (len(playerWords), self._roundSettings['minWordsPerPlayer'])
		return "Ты больше не готов к игре в этом раунде, трусиха" if not Player.setState(player_id=player_id, round_id=self._gameState['round_id']) else \
			"Ты изготовился к игре. Удач!"

	def getCandidates(self, update):
		self._refreshGameState(checkGameStatus=True)

		self._addRandomWord()
		fullInfoWordsList = Word.getListByRoundId(fullAccess=True, **self._gameState['query'])

		wordsByPlayer = dict()
		randomPlayersList = []

		for wordInfo in fullInfoWordsList:

			if wordInfo['telegram_id'] == Base_Game._RANDOM_PLAYER['id'] and Base_Game._RANDOM_PLAYER['id'] not in randomPlayersList:
				randomPlayersList.append(Base_Game._RANDOM_PLAYER['id'])
			if wordInfo['player_id'] not in wordsByPlayer:
				wordsByPlayer[wordInfo['player_id']] = dict(
					words=[],
					isReady=Player.getState(player_id=wordInfo['player_id'], round_id=self._gameState['round_id']),
					name=wordInfo['name'],
					telegram_id=wordInfo['telegram_id'],
					player_id=wordInfo['player_id'],
				)
			wordsByPlayer[wordInfo['player_id']]['words'].append((wordInfo['id'], wordInfo['word'], wordInfo['player_id']))
		unreadyPlayers = [p['name'] for p in wordsByPlayer.values() if not p['isReady'] and p['telegram_id'] != self._RANDOM_PLAYER['id']]

		if len(wordsByPlayer) < self._roundSettings['minPlayers'] + len(randomPlayersList):
			return "Что-то маловато народца набралось для игры (%d/%d). Зови друзей" % (len(wordsByPlayer) - len(randomPlayersList), self._roundSettings['minPlayers'])
		if len(wordsByPlayer) > self._roundSettings['maxPlayers'] - len(randomPlayersList):
			return "Ого сколько вас набежало. Слишком много вас, а я один (%d/%d). Пошли вон!" % (len(wordsByPlayer) + len(randomPlayersList), self._roundSettings['maxPlayers'])
		if unreadyPlayers:
			return "Слишком много тормозов в игре. Я не могу показать тебе словцы, пока все не будут готовы. Список тормозов:\n%s" % " ".join(unreadyPlayers)
		if self._gameState['roundStatus'] == Round.STATUS_PREPARATION:
			Round.updateRoundStatus(round_id=self._gameState['round_id'], status=Round.STATUS_IN_PROGRESS)

		wordsList = self._splitWordsIntoGroups([word for wordsInfo in wordsByPlayer.values() for word in wordsInfo['words']])

		return """
			Вот список всех словцов. Кроме того я добавил в него несколько случайных (а может и нет). Хехе.
			Добавь вместо ноликов свои баллы.
			<b>%s</b>
			Суммарное максимальное количество баллов: %d
			Суммарное минимальное количество баллов: %d
			Максимальное количество баллов на слово: %d
		""" % (
			"\n".join(["Группа %d: %s" % (i, " 0 ".join(w)) for i, w in wordsList.items()]) + " 0",
			self._roundSettings['maxWeightPerRound'],
			self._roundSettings['minWeightPerRound'],
			self._roundSettings['maxWeightPerWord']
		)

	def vote(self, update, weightPlain):
		self._refreshGameState(checkGameStatus=True)
		player_id = Player.getId(update.message.chat)
		if self._gameState['roundStatus'] == Round.STATUS_PREPARATION:
			return "Ещё слишком рано голосовать за словцы! Игра ещё не начата!"
		if self._gameState['roundStatus'] == Round.STATUS_ENDED:
			return "Уже поздновато отдавать свой никчёмный голос. Раунд завернёш. Жди начала следующего!"
		if not re.match(r"^(?:[А-яё]+[\s]*[\d]*[\s]*)+$", weightPlain):
			return "Ну ё-моё, передай мне свои баллы в правильном формате: \"Словцо 4 Словцо 5\""
		weightParsed = re.findall(r"(?P<word>[А-яё]+)[\s]*(?P<weight>[\d]+)", weightPlain)
		responses = []
		weightPlanned = sum([int(weight) for word, weight in weightParsed])
		if weightPlanned > self._roundSettings['maxWeightPerRound']:
			return "Ты распределил слишком много баллов, дурашка (%d/%d)." % (weightPlanned, self._roundSettings['maxWeightPerRound'])
		for word, weight in weightParsed:
			weight = int(weight)
			word_id = Word.getIdByName(word=word, **self._gameState['query'])
			if not word_id:
				return "Охохо! Нет такого словца в этой игре. Совсем. Проголосуй за правильное"
			voteStatus, response = self._isPlayerCanVote(player_id=player_id, weight=weight, word_id=word_id, word=word)
			if response:
				responses.append(response)
			if not voteStatus:
				continue
			Vote.set(word_id=word_id, weight=weight, player_id=player_id, **self._gameState['query'])
			responses.append("Ура! Я успешно записал %d баллов словцу <b>%s</b>." % (weight, word))
		return "\n".join(responses) + ("\nТы просадил <b>%d</b>/%d" % (Vote.getPlayerSumOfWeightPerRound(player_id=player_id, **self._gameState['query']), self._roundSettings['maxWeightPerRound']))

	def getSelfVotes(self, update):
		self._refreshGameState(checkGameStatus=True)
		player_id = Player.getId(update.message.chat)
		overallSpent = Vote.getPlayerSumOfWeightOverall(player_id=player_id)
		lastGameSpent = Vote.getPlayerSumOfWeightPerGame(player_id=player_id, **self._gameState['query'])
		votes, lastRoundSpent = Vote.getPlayerWeightPerRoundByWord(player_id=player_id, **self._gameState['query'])
		return """
			За всё время ты вложил %d очков. За последнюю игру - %d
			В текущем раунде ты потратил %d/%d очков. Спустил ты их на эти словцы:
			<b>%s</b>
		""" % (
			overallSpent,
			lastGameSpent,
			lastRoundSpent,
			self._roundSettings['maxWeightPerRound'], " ".join("%s (%d)" % (vote['word'], vote['weight']) for vote in votes.values() if vote['weight'])
		)

	def _isPlayerCanVote(self, player_id, weight, word_id, word):
		groupNumber, groupWords = Group.getGroupByWord(word_id=word_id, **self._gameState['query'])
		votes, spentWeight = Vote.getPlayerWeightPerRoundByWord(player_id=player_id, **self._gameState['query'])
		if weight > self._roundSettings['maxWeightPerWord']:
			return False, "Нельзя наваливать так много баллов одному словцу (%d/%d)." % (weight, self._roundSettings['maxWeightPerWord'])
		if word_id not in votes and (spentWeight + weight > self._roundSettings['maxWeightPerRound']):
			return False, """
				Я не могу навалить %d баллов словцу <b>%s</b>. Ты уже потратил %d/%d на всякий мусор.
			""" % (weight, word, spentWeight, self._roundSettings['maxWeightPerRound'])
		if spentWeight >= self._roundSettings['maxWeightPerRound']:
			if word_id not in votes:
				return False, """
					Опомнись! Ты уже потратил все свои баллы (%d/%d), чтобы голосовать за слово <b>%s</b>.
				""" % (spentWeight, self._roundSettings['maxWeightPerRound'], word)
			for existedVote in votes.values():
				respentWeight = spentWeight - (existedVote['weight'] - weight)
				if existedVote['word_id'] == word_id and weight > existedVote['weight'] and respentWeight > self._roundSettings['maxWeightPerRound']:
					return False, """
						Да не хватит тебе баллов, что бы повысить вес этого жалкого словца на столько (%d/%d)
					""" % (respentWeight, self._roundSettings['maxWeightPerRound'])
		if groupNumber == -1:
			return False, "Что-то не то. Слово <b>%s</b> найдено сразу в двух группах. Как же так-то?" % word
		if not groupNumber:
			return False, "Не могу найти группу, к которой принадлежит словоцо <b>%s</b>. Буду думать..." % word
		if weight > 0 and \
			Word.isWordBelongToPlayer(player_id=player_id, word=word, **self._gameState['query']) and \
			[word for word in groupWords if not Word.isWordBelongToPlayer(player_id=player_id, word=word, **self._gameState['query'])]:
			return False, """
				Ты совесть-то поимей, подлец.
				Нельзя голосовать за свои словцы (в том числе и за <b>%s</b>), если на выбор есть словцы других игроков
			""" % word
		return True, None

	def _splitWordsIntoGroups(self, words, expelSuperfluousWords=True):
		savedGroups = Group.getGroupWords(**self._gameState['query'])
		if savedGroups:
			return savedGroups
		random.shuffle(words)
		groupSize = len(words) if self._roundSettings['groupSize'] == -1 else self._roundSettings['groupSize']
		groups = OrderedDict((i+1, v) for i, v in enumerate(splitList(words, groupSize)))
		for groupNumber, wordsList in groups.items():
			status = Group.STATUS_EXILE if expelSuperfluousWords and len(wordsList) < self._roundSettings['groupSize'] else Group.STATUS_UNDEFINED
			for wordInfo in wordsList:
				Group.addWordToGroup(
					word_id=wordInfo[0],
					number=groupNumber,
					status=status,
					player_id=wordInfo[2], **self._gameState['query'])
		return OrderedDict((i, [w[1] for w in words]) for i, words in groups.items())

	# def _saveWordIntoGr

	def _addRandomWord(self):
		if 'randomWordsLimit' not in self._roundSettings or not self._roundSettings['randomWordsLimit'] or \
				Word.getListByRoundId(telegram_id=Base_Game._RANDOM_PLAYER['id'], **self._gameState['query']):
			return
		randomWordsCount = 0
		wordsAdded = 0
		while wordsAdded <= self._roundSettings['randomWordsLimit']:
			if randomWordsCount > 20:
				break
			randomWordsCount += 1
			word = self._getRandom("ushakov", wordMinLength=self._roundSettings['minWordsPerPlayer'])
			if not word:
				continue
			Word.add(
				word=word,
				player_id=Player.getId(self._RANDOM_PLAYER),
				wordsLimit=self._roundSettings['randomWordsLimit'],
				wordMinLength=self._roundSettings['minWordLength'],
				**self._gameState['query']
			)
			wordsAdded += 1

	@staticmethod
	def _generatePassword(password):
		if password == Base_Game.PASSWORD_NO_PASSWORD_MARK:
			return None
		password = str(password).strip()
		if len(password) < Base_Game.PASSWORD_MIN_LENGTH:
			raise InvalidPasswordError
		return md5(password + Config.get('MISC.password_salt'))

	def _start(self, words, weights):
		raise NotImplementedError("Method must be override")


class GameWasNotCreateError(Exception):
	pass


class GameWasNotFoundError(Exception):
	pass


class GameWasNotStartError(Exception):
	pass


class SeriesWasNotFoundError(Exception):
	pass


class SeriesAccessDeniedError(Exception):
	pass


class GameAccessDeniedError(Exception):
	pass


class GameIsNotReadyError(Exception):
	pass


class GameAutoCreatingFailedError(Exception):
	pass


class InvalidPasswordError(Exception):
	pass


class CircleGameRefreshingError(Exception):
	pass


class PlayerAddingError(Exception):
	pass
