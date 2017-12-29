from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from libs.coll import bestOfMultipleSmart, md5, Config, buildMenu
from game.player import Player
from game.round import Round
from game.game import Game
from game.series import Series
from game.word import Word
import json
import logging
import random


class Base_Game:

	_SETTINGS = dict(
		round={
			1:
			dict(
				minWordsPerPlayer=1,
				maxWordsPerPlayer=1,
				minWordLength=4,
				maxWordLength=15,
				maxWeightPerWord=4,
				maxWeightPerRound=4,
				minWeightPerRound=4,
				minPlayers=3,
				maxPlayers=20,
				randomWordsLimit=1,
				randomPlayers=1,
				percentPerPoint=5,
				groupSize=-1,  # -1 is auto size
				fightDegree=3.0,
				fightMaxWeight=.9,
				validationRegex=""
			)
		}
	)

	_DICTIONARIES = {
		"ushakov": r"./dictionaries/ushakov_reb.txt"
	}

	_RANDOM_PLAYER = [
		{
			'id': -1,
			'first_name': "Жорж"
		},
		{
			'id': -2,
			'first_name': "Жоржетта"
		}
	]

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
		self._RANDOM_PLAYER_IDS = [x['id'] for x in self._RANDOM_PLAYER]

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

	def getSeriesState(self):
		self._refreshSeriesState()
		return self._seriesState

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

	@staticmethod
	def _generatePassword(password):
		if password == Base_Game.PASSWORD_NO_PASSWORD_MARK:
			return None
		password = str(password).strip()
		if len(password) < Base_Game.PASSWORD_MIN_LENGTH:
			raise InvalidPasswordError
		return md5(password + Config.get('MISC.password_salt'))


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

	def _addRandomWord(self):
		if 'randomPlayers' not in self._roundSettings or not self._roundSettings['randomPlayers']:
			return
		if 'randomWordsLimit' not in self._roundSettings or not self._roundSettings['randomWordsLimit']:
			return
		randomPlayersProcessed = 0
		for randomPlayer in self._RANDOM_PLAYER:
			if randomPlayersProcessed >= self._roundSettings['randomPlayers']:
				break
			if not Player.get(telegram_id=randomPlayer['id']):
				Player.add(telegram_id=randomPlayer['id'], name=randomPlayer['first_name'])
			randomPlayersProcessed += 1
			if Word.getListByRoundId(telegram_id=randomPlayer['id'], **self._gameState['query']):
				continue
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
					player_id=Player.getId(randomPlayer),
					wordsLimit=self._roundSettings['randomWordsLimit'],
					wordMinLength=self._roundSettings['minWordLength'],
					**self._gameState['query']
				)
				wordsAdded += 1

	@staticmethod
	def _start(words, weights):
		raise NotImplementedError


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