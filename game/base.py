from libs.dbAdapter import DB
import logging
import random
from collections import OrderedDict
import re
from libs.coll import splitList
from game.player import Player
from game.word import Word
from game.round import Round
from game.group import Group
from game.vote import Vote
from game.log import Log
import json


class Base_Game:

	ERROR_CODES = {
		"INNER_ERROR": "Ебануться! Что-то пошло не так. Я не смог сохранить твоё словцо. Не делай так больше!"
	}

	_ROUNDS = dict()

	_DICTIONARIES = {
		"ushakov": r"./dictionaries/ushakov_reb.txt"
	}

	_RANDOM_PLAYER = {'id': -1, 'first_name': "Жорж"}

	STATUS_IN_PROGRESS = "in progress"
	STATUS_ENDED = "ended"

	game_id = None
	round_id = None
	roundNumber = None

	def _refreshGameState(self):
		self.game_id, self.round_id = self._getId()
		_round = Round.get(self.round_id)
		self.roundNumber = _round['number']
		self.roundStatus = _round['status']
		self.gameState = dict(
			game_id=self.game_id,
			round_id=self.round_id,
			roundNumber=self.roundNumber,
			roundStatus=self.roundStatus,
			gameCreateDate=self._get(self.game_id)['createDate'].strftime('%Y-%m-%d %H:%M:%S')
		)
		self.roundSettings = self._ROUNDS[self.roundNumber]

	def addWord(self, update):
		self._refreshGameState()
		if self.roundStatus != Round.STATUS_PREPARATION:
			return "Слишком поздно вертеть задом. Раунд уже началася. Дождись окончания раунда"
		return Word.add(
			word=update.message.text,
			player_id=Player.getId(update.message.chat),
			wordsLimit=self.roundSettings['minWordsPerPlayer'],
			wordMinLength=self.roundSettings['minWordLength'],
			**self.gameState
		)[1]

	def start(self):
		self._refreshGameState()
		groups = Group.get(groupByGroupNumber=True, **self.gameState)
		if self.roundStatus != Round.STATUS_IN_PROGRESS:
			return "Не надо огня! Рано ещё начинать рубку. Предлагайте свои словцы и голосуйте за другие"
		# self.isEveryOneVoted()
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
					playerSpentWeight = Vote.getPlayerSumOfWeightPerRound(player_id=info['player_id'], **self.gameState)
					if playerSpentWeight < self.roundSettings['maxWeightPerRound']:
						lazyPlayers[info['player_id']] = dict(name=info['name'], spentWeight=playerSpentWeight)
					if playerSpentWeight > self.roundSettings['maxWeightPerRound']:
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
			"Игра от <b>%(gameCreateDate)s</b>. Раунд <b>%(roundNumber)d</b>" % self.gameState
		]
		winners = []
		for groupNumber, group in preparedGroups.items():
			winnerWord, stats = self._start(group['words'], group['weights'])
			stats['players'] = statsByPlayer
			winners.append(wordsByWord[winnerWord]['player_id'])
			responseList += self._getPrettyGroupResultsList(stats, winnerWord, groupNumber, **self.gameState)
			Log.save(
				data=json.dumps(stats),
				group_id=wordsByWord[winnerWord]['group_id'],
				winnerPlayer_id=wordsByWord[winnerWord]['player_id'],
				winnerWord_id=wordsByWord[winnerWord]['word_id'],
				**self.gameState
			)
		Round.updateRoundStatus(status=Round.STATUS_ENDED, **self.gameState)
		if self.roundNumber + 1 not in self._ROUNDS:
			self._update(status=Base_Game.STATUS_ENDED, winner_id=winners[0] if len(winners) == 1 else None, **self.gameState)
		return "\n".join(responseList)

	@staticmethod
	def _getPrettyGameResults(gamesLog):
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
	def _getPrettyGroupResultsList(stats, winnerWord, groupNumber, **gameState):
		responseList = [
			"<b>Группа %d</b>" % groupNumber,
			# "<b>Баллы:</b>\n%s" % "\n".join(["%d: %s" % (p, w) for w, p in stats['points'].items()]),
			"<b>Вероятности:</b>\n%s" % "\n".join(["%.2f: %s" % (p[1], w) for w, p in stats['weights'].items()]),
			"<b>Слово-победитель:</b> <b>%s</b>" % winnerWord,
			"<b>Игрок-победитель: %s</b>" % Player.getPlayerByWord(word=winnerWord, **gameState)['name'],
			"<b>Участники:</b>",
		]
		for playerInfo in stats['players'].values():
			responseList.append("<b>%s</b>" % playerInfo['name'])
			for word, wordInfo in playerInfo['words'].items():
				responseList.append("* %s (%d)" % (word, sum([e['weight'] for e in wordInfo.values()])))
				for elector in wordInfo.values():
					responseList.append("++ %s: %d" % (elector['name'], elector['weight']))
		return responseList

	def updateWord(self, oldWord, newWord, update):
		self._refreshGameState()
		player_id = Player.getId(update.message.chat)
		if self.roundStatus == Round.STATUS_IN_PROGRESS:
			return "Ахаха. Раунд-то уже начался. Поздно теперь крутить себе соски. Надейся на лучшее!"
		if Player.getState(player_id=player_id, **self.gameState):
			return "Ты не можешь обновить своё убогое словцо, если ты уже приготовился играть, вонючка!"
		return Word.update(
			oldWord=oldWord,
			newWord=newWord,
			player_id=player_id,
			wordMinLength=self.roundSettings['minWordLength'],
			**self.gameState
		)

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
	def getLastGameLog(status=STATUS_ENDED):
		return Base_Game.getGameLog(game_id=None, status=status)

	@staticmethod
	def getGameLog(game_id, status=STATUS_ENDED):
		log = Base_Game._getGameLog(game_id=game_id, status=status)
		if not log:
			return (
				("Не получается найти лог игры с ID <b>%d</b>." % game_id) if game_id
				else "Не получается найти лог последней игры.") \
				+ " Возможно, игра ещё не была завершена?"
		return Base_Game._getPrettyGameResults(log)

	@staticmethod
	def _getGameLog(**params):
		game = Base_Game._get(**params)
		if not game:
			return None
		return Log.get(game_id=game['id'])

	def getPlayerWordsByRound(self, update, round_id=None, fullAccess=False):
		self._refreshGameState()
		player_id = Player.getId(update.message.chat)
		return Word.getListByRoundId(
			fullAccess=fullAccess,
			round_id=round_id,
			player_id=player_id
		) if round_id else Word.getListByRoundId(
				fullAccess=fullAccess,
				player_id=player_id,
				**self.gameState
			)

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
			word = random.choice(list(open(self._DICTIONARIES[dictionaryName], encoding="utf-8")))
			if Word.isWordValid(word, minLength)[0]:
				return word
		return None

	def setPlayerState(self, update):
		self._refreshGameState()
		if self.roundStatus != Round.STATUS_PREPARATION:
			return "Поздняк метаться. Раунд уже запущен. Молись!"
		player_id = Player.getId(update.message.chat)
		playerWords = Word.getListByRoundId(player_id=player_id, **self.gameState)
		if len(playerWords) < self.roundSettings['minWordsPerPlayer']:
			return "Надо предложить побольше словцов, чтобы быть готовым. Осталось предложить: %d/%d" % (len(playerWords), self.roundSettings['minWordsPerPlayer'])
		return "Ты больше не готов к игре в этом раунде, трусиха" if not Player.setState(player_id=player_id, round_id=self.round_id) else \
			"Ты изготовился к игре. Удач!"

	def getCandidates(self, update):
		self._refreshGameState()
		fullInfoWordsList = Word.getListByRoundId(fullAccess=True, **self.gameState)
		wordsByPlayer = dict()
		self._addRandomWord()
		randomPlayersList = []
		for wordInfo in fullInfoWordsList:
			if wordInfo['telegram_id'] == Base_Game._RANDOM_PLAYER['id'] and Base_Game._RANDOM_PLAYER['id'] not in randomPlayersList:
				randomPlayersList.append(Base_Game._RANDOM_PLAYER['id'])
			if wordInfo['player_id'] not in wordsByPlayer:
				wordsByPlayer[wordInfo['player_id']] = dict(
					words=[],
					isReady=Player.getState(player_id=wordInfo['player_id'], round_id=self.round_id),
					name=wordInfo['name'],
					telegram_id=wordInfo['telegram_id'],
					player_id=wordInfo['player_id'],
				)
			wordsByPlayer[wordInfo['player_id']]['words'].append((wordInfo['id'], wordInfo['word'], wordInfo['player_id']))
		unreadyPlayers = [p['name'] for p in wordsByPlayer.values() if not p['isReady'] and p['telegram_id'] != self._RANDOM_PLAYER['id']]
		if len(wordsByPlayer) < self.roundSettings['minPlayers'] + len(randomPlayersList):
			return "Что-то маловато народца набралось для игры (%d/%d). Зови друзей" % (len(wordsByPlayer) - len(randomPlayersList), self.roundSettings['minPlayers'])
		if len(wordsByPlayer) > self.roundSettings['maxPlayers'] - len(randomPlayersList):
			return "Ого сколько вас набежало. Слишком много вас, а я один (%d/%d). Пошли вон!" % (len(wordsByPlayer) + len(randomPlayersList), self.roundSettings['maxPlayers'])
		if unreadyPlayers:
			return "Слишком много тормозов в игре. Я не могу показать тебе словцы, пока все не будут готовы. Список тормозов:\n%s" % " ".join(unreadyPlayers)
		if self.roundStatus == Round.STATUS_PREPARATION:
			Round.updateRoundStatus(round_id=self.round_id, status=Round.STATUS_IN_PROGRESS)
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
			self.roundSettings['maxWeightPerRound'],
			self.roundSettings['minWeightPerRound'],
			self.roundSettings['maxWeightPerWord']
		)

	def vote(self, update, weightPlain):
		self._refreshGameState()
		player_id = Player.getId(update.message.chat)
		if self.roundStatus == Round.STATUS_PREPARATION:
			return "Ещё слишком рано голосовать за словцы! Игра ещё не начата!"
		if self.roundStatus == Round.STATUS_ENDED:
			return "Уже поздновато отдавать свой никчёмный голос. Раунд завернёш. Жди начала следующего!"
		if not re.match(r"^(?:[А-яё]+[\s]*[\d]*[\s]*)+$", weightPlain):
			return "Ну ё-моё, передай мне свои баллы в правильном формате: \"Словцо 4 Словцо 5\""
		weightParsed = re.findall(r"(?P<word>[А-яё]+)[\s]*(?P<weight>[\d]+)", weightPlain)
		responses = []
		weightPlanned = sum([int(weight) for word, weight in weightParsed])
		if weightPlanned > self.roundSettings['maxWeightPerRound']:
			return "Ты распределил слишком много баллов, дурашка (%d/%d)." % (weightPlanned, self.roundSettings['maxWeightPerRound'])
		for word, weight in weightParsed:
			weight = int(weight)
			word_id = Word.getIdByName(word=word, **self.gameState)
			voteStatus, response = self._isPlayerCanVote(player_id=player_id, weight=weight, word_id=word_id, word=word)
			if response:
				responses.append(response)
			if not voteStatus:
				continue
			Vote.set(word_id=word_id, weight=weight, player_id=player_id, **self.gameState)
			responses.append("Ура! Я успешно записал %d баллов словцу <b>%s</b>." % (weight, word))
		return "\n".join(responses) + ("\nТы просадил <b>%d</b>/%d" % (Vote.getPlayerSumOfWeightPerRound(player_id=player_id, **self.gameState), self.roundSettings['maxWeightPerRound']))

	def getSelfVotes(self, update):
		self._refreshGameState()
		player_id = Player.getId(update.message.chat)
		overallSpent = Vote.getPlayerSumOfWeightOverall(player_id=player_id)
		lastGameSpent = Vote.getPlayerSumOfWeightPerGame(player_id=player_id, **self.gameState)
		votes, lastRoundSpent = Vote.getPlayerWeightPerRoundByWord(player_id=player_id, **self.gameState)
		return """
			За всё время ты вложил %d очков. За последнюю игру - %d
			В текущем раунде ты потратил %d/%d очков. Спустил ты их на эти словцы:
			<b>%s</b>
		""" % (
			overallSpent,
			lastGameSpent,
			lastRoundSpent,
			self.roundSettings['maxWeightPerRound'], " ".join("%s (%d)" % (vote['word'], vote['weight']) for vote in votes.values() if vote['weight'])
		)

	def _getPlainPlayersWeights(self):
		self._refreshGameState()
		responseList = []
		playerVotes, votesSum = Vote.getWeightPerRoundByPlayer(**self.gameState)
		responseList.append("Игроки поставили такие баллы:")
		responseList += ["%s: %s (<b>%d</b>)" % (name, vote['word'], vote['weight']) for name, votes in playerVotes.items() for vote in votes if vote['weight'] > 0]
		responseList.append("Всего поставлено <b>%d</b> баллов" % votesSum)
		return responseList

	def _isPlayerCanVote(self, player_id, weight, word_id, word):
		self._refreshGameState()
		groupNumber, groupWords = Group.getGroupByWord(word_id=word_id, **self.gameState)
		votes, spentWeight = Vote.getPlayerWeightPerRoundByWord(player_id=player_id, **self.gameState)
		if weight > self.roundSettings['maxWeightPerWord']:
			return False, "Нельзя наваливать так много баллов одному словцу (%d/%d)." % (weight, self.roundSettings['maxWeightPerWord'])
		if word_id not in votes and (spentWeight + weight > self.roundSettings['maxWeightPerRound']):
			return False, """
				Я не могу навалить %d баллов словцу <b>%s</b>. Ты уже потратил %d/%d на всякий мусор.
			""" % (weight, word, spentWeight, self.roundSettings['maxWeightPerRound'])
		if spentWeight >= self.roundSettings['maxWeightPerRound']:
			if word_id not in votes:
				return False, """
					Опомнись! Ты уже потратил все свои баллы (%d/%d), чтобы голосовать за слово <b>%s</b>.
				""" % (spentWeight, self.roundSettings['maxWeightPerRound'], word)
			for existedVote in votes.values():
				respentWeight = spentWeight - (existedVote['weight'] - weight)
				if existedVote['word_id'] == word_id and weight > existedVote['weight'] and respentWeight > self.roundSettings['maxWeightPerRound']:
					return False, """
						Да не хватит тебе баллов, что бы повысить вес этого жалкого словца на столько (%d/%d)
					""" % (respentWeight, self.roundSettings['maxWeightPerRound'])
		if groupNumber == -1:
			return False, "Что-то не то. Слово <b>%s</b> найдено сразу в двух группах. Как же так-то?" % word
		if not groupNumber:
			return False, "Не могу найти группу, к которой принадлежит словоцо <b>%s</b>. Буду думать..." % word
		if weight > 0 and \
			Word.isWordBelongToPlayer(player_id=player_id, word=word, **self.gameState) and \
			[word for word in groupWords if not Word.isWordBelongToPlayer(player_id=player_id, word=word, **self.gameState)]:
			return False, """
				Ты совесть-то поимей, подлец.
				Нельзя голосовать за свои словцы (в том числе и за <b>%s</b>), если на выбор есть словцы других игроков
			""" % word
		return True, None

	def _splitWordsIntoGroups(self, words, expelSuperfluousWords=True):
		self._refreshGameState()
		savedGroups = Group.getGroupWords(**self.gameState)
		if savedGroups:
			return savedGroups
		random.shuffle(words)
		groupSize = len(words) if self.roundSettings['groupSize'] == -1 else self.roundSettings['groupSize']
		groups = OrderedDict((i+1, v) for i, v in enumerate(splitList(words, groupSize)))
		for groupNumber, wordsList in groups.items():
			status = Group.STATUS_EXILE if expelSuperfluousWords and len(wordsList) < self.roundSettings['groupSize'] else Group.STATUS_UNDEFINED
			for wordInfo in wordsList:
				Group.addWordToGroup(word_id=wordInfo[0], number=groupNumber, status=status, player_id=wordInfo[2], **self.gameState)
		return OrderedDict((i, [w[1] for w in words]) for i, words in groups.items())

	# def _saveWordIntoGr

	def _addRandomWord(self):
		if 'randomWordsLimit' not in self.roundSettings or not self.roundSettings['randomWordsLimit'] or \
				Word.getListByRoundId(telegram_id=Base_Game._RANDOM_PLAYER['id'], **self.gameState):
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
			Word.add(
				word=word,
				player_id=Player.getId(self._RANDOM_PLAYER),
				wordsLimit=self.roundSettings['minWordsPerPlayer'],
				wordMinLength=self.roundSettings['minWordLength'],
				**self.gameState
			)
			wordsAdded += 1

	@staticmethod
	def _init():
		game_id = DB.execute("INSERT INTO game SET createDate = NOW()").lastrowid
		logging.info("New game was started. ID: %d" % game_id)
		# addRandomPlayer
		return game_id

	@staticmethod
	def _getId(game_id=None, doNotInitNewGame=False):
		condition = ("status = '%s'" % Base_Game.STATUS_IN_PROGRESS) if not game_id else " AND id = %d" % game_id
		game = DB.getOne("SELECT * FROM game WHERE %s ORDER BY id DESC" % condition)
		if doNotInitNewGame and not game:
			return None
		game_id = Base_Game._init() if not game else game['id']
		return game_id, Round.getId(game_id)

	@staticmethod
	def _get(game_id=None, status=None):
		if not game_id and not status:
			return None
		condition = ""
		if status:
			condition += " AND status = '%s'" % status
		if game_id:
			condition += " AND id = %d" % game_id
		return DB.getOne("SELECT * FROM game WHERE 1 " + condition + " ORDER BY id DESC")

	@staticmethod
	def _update(**params):
		return DB.execute("UPDATE game SET winner_id = %(winner_id)s, status = %(status)s WHERE id = %(game_id)s", params)

	def _start(self, words, weights):
		raise NotImplementedError("Method must be override")

