from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
# from telegram import ReplyKeyboardRemove
import logging
from game.type.perfectWord import Perfect_Word
from game.type.base import Base_Game
from game.type.base import GameWasNotStartError, GameWasNotFoundError, GameWasNotCreateError, GameAccessDeniedError, \
	SeriesWasNotFoundError, SeriesAccessDeniedError, InvalidPasswordError, GameIsNotReadyError
import re
from libs.coll import Config, parseStringArgs, ArgumentParserError
from functools import wraps

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)


updater = Updater(token=Config.get('TELEGRAM.token'))
dispatcher = updater.dispatcher

_RESTRICTION_ADMINS_ONLY = False


def general(func):
	@wraps(func)
	def wrapped(bot, update, *args, **kwargs):
		baseGame = Base_Game(update)
		seriesState = baseGame.getSeriesState()
		if not seriesState or "gameType" not in seriesState['settings'] or seriesState['settings']['gameType'] == "perfectWord":
			game = Perfect_Word(update)
		elif seriesState['settings']['gameType'] == "gallows":
			pass
		else:
			raise GameTypeWasNotFound
		logging.info(update)
		if _RESTRICTION_ADMINS_ONLY and str(update.effective_user.id) not in Config.get('TELEGRAM.admins'):
			sendMsg(bot, update, "Со мной что-то делают. Отвали!")
			return
		try:
			return func(game, bot, update, *args, **kwargs)
		except GameWasNotFoundError:
			sendMsg(bot, update, "О-хо-хо! Ты до сих пор не поучаствовал ни в одной игре!\nСоздай новую командой /gamecreate или просоединись к существующей - /gamejoin")
			return
		except GameWasNotCreateError:
			sendMsg(bot, update, "Последняя игра серии была завершена.\nСоздай новую командой /gamecreate или просоединись к существующей - /gamejoin")
			return
		except GameWasNotStartError:
			sendMsg(bot, update, "Игра найдена, но её создатель ещё не решился её начать")
			return
		except SeriesWasNotFoundError:
			sendMsg(bot, update, "Прежде чем начать играть, надо присоединиться к какой-нибудь серии игр. Для списка доступных серий наберите /serieslist")
			return
		except SeriesAccessDeniedError:
			sendMsg(bot, update, "Тебе не рады в серии игр. Попробуй ввести правильный пароль")
			return
		except GameAccessDeniedError:
			sendMsg(bot, update, "Тебе не рады этой игре. Попробуй ввести правильный пароль")
			return
		except GameIsNotReadyError:
			sendMsg(bot, update, "Создатель игры ещё не настроил её правила. Пни его!")
			return
		except Exception:
			sendMsg(bot, update, "Ааааа! Как больно, БОЛЬНО! Агония! Я страдаю. Зачем ты так делаешь?! Не детай так, прошу!")
			raise

	return wrapped


@general
def start(game, bot, update):
	sendMsg(bot, update, commandsList)


@general
def getPlayerStatus(game, bot, update):
	sendMsg(bot, update, game.getPlayerStatus())


@general
def createGame(game, bot, update):
	response = game.createGame()
	return sendMsg(bot, update, response)


@general
def startGame(game, bot, update):
	response = game.startGame()
	return sendMsg(bot, update, response)


@general
def joinGame(game, bot, update, args):
	try:
		game_id = int(args[0]) if args else None
		password = str(args[1]) if len(args) > 1 else None
	except (ValueError, IndexError):
		sendMsg(bot, update, "ID серии - число, блин.")
		return
	response = game.joinGame(game_id, password)[1]
	return sendMsg(bot, update, response)


@general
def getGameSettings(game, bot, update):
	response = game.getGameSettings()
	return sendMsg(bot, update, response)


@general
def setGameSettings(game, bot, update, args):
	if not args:
		response = game.getGameSettingsButtons()
		return sendMsg(bot, update, response)

	if len(args) != 3:
		sendMsg(bot, update, "Задай настройки в правильном формате!\nПравильный формат таков:\nНОМЕР_РАУНДА ПАРАМЕТР ЗНАЧЕНИЕ")
		return

	try:
		roundNumber = int(args[0])
	except ValueError:
		sendMsg(bot, update, "Номер раунда - число, блин.")
		return

	response = game.setGameSettings(
		roundNumber=roundNumber,
		name=args[1],
		value=args[2]
	)
	return sendMsg(bot, update, response)


@general
def setGameSettingsButton(game, bot, update):
	query = update.callback_query
	queryArgs = query.data.split(" ")
	response = game.setGameSettings(
		roundNumber=int(queryArgs[0]),
		name=queryArgs[1],
		value=queryArgs[2]
	)
	bot.edit_message_text(
		text=response['msg'],
		chat_id=query.message.chat_id,
		message_id=query.message.message_id,
		parse_mode="html",
		reply_markup=response['buttons']
	)


@general
def setGamePassword(game, bot, update, args):
	if not args:
		response = "Передай пароль. Если хочешь убрать пароль, то введи \"%s\"" % game.PASSWORD_NO_PASSWORD_MARK
	else:
		if len(args) > 1:
			response = "Нельзя использовать пробелы!"
		else:
			try:
				response = game.setGamePassword(args[0] if args else None)
			except InvalidPasswordError:
				response = "Плохой пароль задал. Минимальная длина пароля - %d символа" % game.PASSWORD_MIN_LENGTH
	return sendMsg(bot, update, response)


@general
def joinSeries(game, bot, update, args):
	try:
		series_id = int(args[0])
		password = str(args[1]) if len(args) > 1 else None
	except (ValueError, IndexError):
		sendMsg(bot, update, "ID серии - число, блин.")
		return
	response = game.joinSeries(series_id, password)
	sendMsg(bot, update, response)


@general
def getSeriesList(game, bot, update):
	sendMsg(bot, update, game.getSeriesList())


@general
def catchWord(game, bot, update):
	response = game.addWord(update)
	sendMsg(bot, update, response)


@general
def showMyWordsPerGame(game, bot, update, args):
	game_id = int(args[0]) if args else None
	wordsList = game.getPlayerWordsByGame()
	if not wordsList:
		response = "Какой стыд. Ты не смог предложить ни одного словца за всю игру!"
		sendMsg(bot, update, response)
		return
	response = """Вон они, твои словцы. Делай с ними теперь что хочешь:\n%s""" % " ".join(w['word'] for w in wordsList)
	sendMsg(bot, update, response)


@general
def showMyWordsPerRound(game, bot, update, args):
	round_id = int(args[0]) if args else None
	wordsList = game.getPlayerWordsByRound(round_id)
	if not wordsList:
		response = "Какой стыд. Ты не смог предложить ни одного словца за целый раунд!"
		sendMsg(bot, update, response)
		return
	response = """Вон они, твои словцы. Делай с ними теперь что хочешь:\n%s""" % " ".join(w['word'] for w in wordsList)
	sendMsg(bot, update, response)


@general
def updateMyWord(game, bot, update, args):
	if len(args) != 2:
		response = "Слева - старое словцо, справа - новое словцо. ДЕЛАЙ ТАК!"
		sendMsg(bot, update, response)
		return
	response = game.updateWord(update, args[0], args[1])
	sendMsg(bot, update, response)


@general
def getRandomWord(game, bot, update):
	word = game.getRandom('ushakov')
	if not word:
		response = "Очень странно. Не могу получить случайное словцо!"
	else:
		response = "Вот твоё случайное словцо:\n<b>%s</b>" % word.lower()
	response += "Попробуй ещё: /r"
	sendMsg(bot, update, response)


@general
def generateBattle(game, bot, update, args):
	if not args:
		sendMsg(bot, update, """
			Живо передал параметры битвы в правильном формате! Примерно так: "/gb ЧИСЛО_СЛОВ ПАРАМЕТРЫ"
			Поддерживаемые ПАРАМЕТРЫ:			
			-e E - степень
			-m M - максимальный вес
			-p P - веса слов через пробел
			""")
		return
	try:
		wordsLimit = int(args[0])
	except ValueError:
		sendMsg(bot, update, "Количество слов - число, блин.")
		return
	if wordsLimit == 1:
		sendMsg(bot, update, "Что, правда хочешь устроить бой из одного словца?! Какой-то ты неразумный.")
		return
	battleArgs = [
		dict(
			name=["-p"],
			params=dict(
				type=int,
				nargs="*",
				default=[],
				help="Баллы, чере пробел"
			)
		),
		dict(
			name=["-e"],
			params=dict(
				type=float,
				default=3,
				help="Степень"
			)
		),
		dict(
			name=["-m"],
			params=dict(
				type=float,
				default=.9,
				help="Максимальный вес"
			)
		)
	]
	params = None
	weights = []
	if len(args) > 1:
		try:
			params = parseStringArgs(args[1:], battleArgs)
		except ArgumentParserError as err:
			sendMsg(bot, update, """
				Какие-то ты кривые аргументы ввёл. Вот, почитай: %s
				Поддерживаемые аргументы:
				-e E - степень
				-m M - максимальный вес
				-p P - веса слов через пробел
			""" % str(err))
			return
		if not params:
			sendMsg(bot, update, """
				Поддерживаемые аргументы:\n
				-e E - степень\n
				-m M - максимальный вес\n
				-p P - веса слов через пробел
			""")
	if params:
		if not params['p']:
			sendMsg(bot, update, "Ты не передал веса слов! Будет полный хаос!!!\nЕсли хочешь передать веса используй параметр -p и пиши их через пробел")
		weights = params['p']
		del params['p']
	response = game.generate(wordsLimit, weights, params)
	sendMsg(bot, update, response)


@general
def getGameInfo(game, bot, update, args):
	if not args:
		game_id = None
	else:
		if not re.match(r"^[\d]+$", args[0]):
			response = """Очень плохой game_id. Просто отвратительный! game_id состоит только из цифр, болван!
			Если хочешь посмотреть информацию о текущей игре, то не передавай ничего."""
			sendMsg(bot, update, response)
			return
		game_id = int(args[0])
	gameInfo = game.get(game_id)
	if not gameInfo:
		sendMsg(bot, update, "Невероятно! До сих пор не было запущено ни одной игры!")
		return
	response = """
	Сейчас идёт игра, начатая %(createDate)s. ID игры: %(id)d
	Всего предложено: %(words)s слов
	Всего инициировано: %(roundsCount)s раундов. Номера раундов: %(roundsNumber)s
	Последний раунд: %(lastRoundNumber)s, запущенный в %(lastRoundCreateDate)s. В нём предложено %(lastRoundWords)s слов
	Участники последнего раунда:\n%(lastRoundPlayersPlain)s
	""" % gameInfo
	sendMsg(bot, update, response)


@general
def getGameList(game, bot, update, args):
	limit = 10
	if args:
		try:
			limit = int(args[0])
		except ValueError:
			sendMsg(bot, update, "Количество игр - число, блин.")
			return
	response = game.getList(limit)
	sendMsg(bot, update, response)


@general
def setState(game, bot, update):
	response = game.setPlayerState(update)
	sendMsg(bot, update, response)


@general
def fight(game, bot, update):
	response = game.start()
	sendMsg(bot, update, response)


@general
def getGameResults(game, bot, update, args):
	if not args:
		game_id = None
	elif len(args) > 1:
		return """
			Укажи ID <b>одной</b> игры, результаты которой ты хочешь посмотреть.
			Или оставь поле пустым, чтобы посмотреть результаты последней игры
		"""
	else:
		try:
			game_id = int(args[0])
		except ValueError:
			sendMsg(bot, update, "ID игры состоит из одних цифр, дуралей.")
			return
	response = game.getLastGameLog() if not game_id else game.getGameLog(game_id)
	sendMsg(bot, update, response)


@general
def getCandidates(game, bot, update):
	response = game.getCandidates(update)
	sendMsg(bot, update, response)


@general
def vote(game, bot, update, args):
	string = ' '.join(args).lower()
	if not string:
		response = """
			Ну ты чё. Скинь непустую строчку со своими баллами в формате: \"Словцо 1 Словцо 5 Словцо 2\".
			Где \"Словцо\" - название словца, а циферки - твои баллы.
		"""
	else:
		response = game.vote(update, string)
	sendMsg(bot, update, response)


@general
def getMyVotes(game, bot, update):
	response = game.getSelfVotes(update)
	sendMsg(bot, update, response)


@general
def iAmSoStupid(game, bot, update):
	text = update.message.text
	failMsg = "Говори на понятном мне языке. Используй понятные слова.\nВот тебе инструкция: /help"
	if text and "_" in text:
		params = text.split("_")
		if len(params) != 2:
			sendMsg(bot, update, failMsg)
			return
		if params[0] == "/gr":
			return getGameResults(bot, update, [params[1]])
	sendMsg(bot, update, failMsg)


def sendMsg(bot, update, msg):
	msgList = [msg] if isinstance(msg, str) else msg
	bufferedMsg = []
	for msg in msgList:
		if isinstance(msg, dict):
			if bufferedMsg:
				_sendMsg(bot=bot, update=update, msg=bufferedMsg)
				bufferedMsg = []
			if 'buttons' in msg:
				bot.send_message(chat_id=update.message.chat_id, text=msg['msg'], parse_mode="html", reply_markup=msg['buttons'])
		else:
			bufferedMsg.append(msg)
	if bufferedMsg:
		_sendMsg(bot=bot, update=update, msg=bufferedMsg)


def _sendMsg(bot, update, msg, **kwargs):
	# reply_markup = ReplyKeyboardRemove()
	# bot.send_message(chat_id=update.message.chat_id, text="I'm back.", reply_markup=reply_markup)
	if isinstance(msg, list):
		msg = "\n".join(msg)
	msgText = re.sub(r"(?<=\n)[\s]+", "", msg) if msg else "Мне нечего тебе сказать, чёрт возьми!"
	bot.send_message(chat_id=update.message.chat_id, text=msgText, parse_mode="html", **kwargs)

[
	dispatcher.add_handler(handler) for handler in [
		CommandHandler(['start', 'help', 'h', 'помощь'], start),
		CommandHandler(['status', 's', 'с', 'статус'], getPlayerStatus),
		CommandHandler(['gameinfo', 'gi', 'играинфо'], getGameInfo, pass_args=True),
		CommandHandler(['gamelist', 'gl', 'играсписок'], getGameList, pass_args=True),
		CommandHandler(['gamecreate', 'gc', 'играсоздать'], createGame),
		CommandHandler(['gamesetpassword', 'gsp', 'игразадатьпароль'], setGamePassword, pass_args=True),
		CommandHandler(['gameset', 'gs', 'игранастроить'], setGameSettings, pass_args=True),
		CommandHandler(['gamestart', 'gstart', 'играначать'], startGame),
		CommandHandler(['gamejoin', 'gj', 'играприсоединиться'], joinGame, pass_args=True),
		CommandHandler(['gamesettings', 'gst', 'игранастройки'], getGameSettings),
		CallbackQueryHandler(setGameSettingsButton),
		CommandHandler(['seriesjoin', 'sj', 'серияприсоединиться'], joinSeries, pass_args=True),
		CommandHandler(['serieslist', 'sl', 'серияспиок'], getSeriesList),
		CommandHandler(['mywordsbygame', 'wg', 'моисловаигра'], showMyWordsPerGame, pass_args=True),
		CommandHandler(['mywordsbyround', 'wr', 'моисловараунд'], showMyWordsPerRound, pass_args=True),
		CommandHandler(['update', 'u', 'обновить', 'о'], updateMyWord, pass_args=True),
		CommandHandler(['random', 'r', 'случайное'], getRandomWord),
		CommandHandler(['fight', 'f', 'битва', 'б'], fight),
		CommandHandler(['candidates', 'c', 'к', 'кандидаты'], getCandidates),
		CommandHandler(['ready', 'готов'], setState),
		CommandHandler(['vote', 'v', 'голос', 'г'], vote, pass_args=True),
		CommandHandler(['voteinfo', 'vi', 'голосинфо', 'ги'], getMyVotes),
		CommandHandler(['gameresult', 'gr', 'результатыигры', 'ри'], getGameResults, pass_args=True),
		CommandHandler(['generatebattle', 'gb', 'генерироватьбитву', 'гб'], generateBattle, pass_args=True),
		MessageHandler(Filters.text, catchWord),


		MessageHandler(Filters.command, iAmSoStupid)
	]
]


def getPlainCommandsList():
	return re.sub(r"/([A-z]+[\s]+)[^-]+", r"\1", commandsList)


commandsList = """
/candidates /c /к /кандидаты - посмотреть список словцов-кандидатов
/fight /f /битва, /б - инициировать выбор лучшего словца. Бой не начнётся, пока все, предложившие словцы, не потратят все баллы
/gameinfo /gi /играинфо - информация о текущей игре
/gamelist /gl /играсписок - получить информацию о последних N играх
/gameresult /gr /результатыиигры /ри - посмотреть результаты игры. Если ID игры не передан, то будут показаны результаты последней игр
/generatebattle /gb /генерироватьбитву /гб - сгенерируй битву и посмотри на результаты! Формат: КОЛИЧЕСТВО_СЛОВ ВЕСА_СЛОВ_ЧЕРЕЗ_ЗАПЯТУЮ ПАРАМЕТРЫ
/mywordsbygame /wg /моисловаигра - твои словцы за текущую игру
/mywordsbyround /wr /моисловараунд - твои словцы за текущий раунд
/random /r /случайное - случайное словцо. Вдохновись!
/ready /готов - говорит мне, что вы готовы/не готовы к мясорубке
/update /u /обновить /о - обнови своё словцо!
/vote /v /голос /г - проголосовать за понравившиеся словцы
/voteinfo /vi /голосинфо /ги - посмотреть информацию о своих баллах
/start /help /h /помощь - помощь и список команд
"""

if __name__ == "__main__":
	updater.start_polling()
	# print(getPlainCommandsList())
	# string = "-f 15"
	# args = [
	# 	dict(
	# 		name=["-e"],
	# 		params=dict(
	# 			type=int
	# 		)
	# 	)
	# ]
	# print(parseStringArgs(string, args))
	# print("1111")

# DELETE FROM words.word WHERE id >= 1;
# DELETE FROM words.game WHERE id >= 1;
# DELETE FROM words.player WHERE id >= 1;
# DELETE FROM words.round WHERE id >= 1;
# DELETE FROM words.groups WHERE id >= 1;
# DELETE FROM words.player_state WHERE id >= 1;
# INSERT INTO player SET name = "Жорж", telegram_id = -1;


class GameTypeWasNotFound(Exception):
	pass
