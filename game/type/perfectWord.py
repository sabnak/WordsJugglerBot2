from libs.dbAdapter import DB
import random
from collections import OrderedDict
from libs.coll import bestOfMultipleSmart
import re
from libs.coll import splitList
from game.type.base import Base_Game
from game.player import Player
from game.word import Word
from game.round import Round
from game.group import Group
from game.vote import Vote
from game.log import Log
from game.game import Game
import json


class Perfect_Word(Base_Game):

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
				if info['telegram_id'] not in self._RANDOM_PLAYER_IDS:
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
				status=Perfect_Word.STATUS_ENDED,
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
					responseList += Perfect_Word._getPrettyGroupResultsList(
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
			responseList.append("Лог игры: /gr_%d" % game['id'])
			responseList.append("Автор: <b>%s</b>" % game['creator_name'])
			responseList.append("Победитель: <b>%s (%s)</b>" % (game['winner_name'], game['word']))
			responseList.append("<pre></pre>")
		return "\n".join(responseList)

	def getLastGameLog(self):
		lastGame = Game.getLastGameInSeries(series_id=self._playerState['series_id'], status=Game.STATUS_ENDED)
		if not lastGame:
			return "Не получается найти лог последней игры.\nВозможно, игра ещё не была завершена?"
		return Perfect_Word.getGameLog(game_id=lastGame['id'])

	@staticmethod
	def getGameLog(game_id):
		log = Perfect_Word._getGameLog(game_id=game_id)
		if not log:
			return "Не получается найти лог игры с ID <b>%d</b>." % game_id
		return Perfect_Word._getPrettyGameResults(log)

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

			if wordInfo['telegram_id'] in self._RANDOM_PLAYER_IDS and wordInfo['telegram_id'] not in randomPlayersList:
				randomPlayersList.append(wordInfo['telegram_id'])
			if wordInfo['player_id'] not in wordsByPlayer:
				wordsByPlayer[wordInfo['player_id']] = dict(
					words=[],
					isReady=Player.getState(player_id=wordInfo['player_id'], round_id=self._gameState['round_id']),
					name=wordInfo['name'],
					telegram_id=wordInfo['telegram_id'],
					player_id=wordInfo['player_id'],
				)
			wordsByPlayer[wordInfo['player_id']]['words'].append((wordInfo['id'], wordInfo['word'], wordInfo['player_id']))

		unreadyPlayers = [p['name'] for p in wordsByPlayer.values() if not p['isReady'] and p['telegram_id'] not in self._RANDOM_PLAYER_IDS]

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

	@staticmethod
	def _start(words, weights):
		winnerWord, stats = bestOfMultipleSmart(words, weights)
		return winnerWord, stats

