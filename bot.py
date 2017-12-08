from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import logging
from game.typeA import Game
import re
from libs.coll import Config, parseStringArgs, ArgumentParserError

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)


updater = Updater(token=Config.get('TELEGRAM.token'))
dispatcher = updater.dispatcher
game = Game()


def start(bot, update):
	logging.info(update)
	sendMsg(bot, update, commandsList)


def catchWord(bot, update):
	logging.info(update)
	response = game.addWord(update)
	sendMsg(bot, update, response)


def iAmSoStupid(bot, update):
	sendMsg(bot, update, "Говори на понятном мне языке. Используй понятные слова.\nВот тебе инструкция: /help")


def showMyWordsPerGame(bot, update, args):
	logging.info(update)
	game_id = int(args[0]) if args else None
	wordsList = game.getPlayerWordsByGame(update, game_id)
	if not wordsList:
		response = "Какой стыд. Ты не смог предложить ни одного словца за всю игру!"
		sendMsg(bot, update, response)
		return
	response = """Вон они, твои словцы. Делай с ними теперь что хочешь:\n%s""" % " ".join(w['word'] for w in wordsList)
	sendMsg(bot, update, response)


def showMyWordsPerRound(bot, update, args):
	logging.info(update)
	round_id = int(args[0]) if args else None
	wordsList = game.getPlayerWordsByRound(update, round_id)
	if not wordsList:
		response = "Какой стыд. Ты не смог предложить ни одного словца за целый раунд!"
		sendMsg(bot, update, response)
		return
	response = """Вон они, твои словцы. Делай с ними теперь что хочешь:\n%s""" % " ".join(w['word'] for w in wordsList)
	sendMsg(bot, update, response)


def updateMyWord(bot, update, args):
	logging.info(update)
	if len(args) != 2:
		response = "Слева - старое словцо, справа - новое словцо. ДЕЛАЙ ТАК!"
		sendMsg(bot, update, response)
		return
	response = game.updateWord(update, args[0], args[1])
	sendMsg(bot, update, response)


def getRandomWord(bot, update):
	logging.info(update)
	word = game.getRandom('ushakov')
	if not word:
		response = "Очень странно. Не могу получить случайное словцо!"
	else:
		response = "Вот твоё случайное словцо:\n<b>%s</b>" % word.lower()
	response += "Попробуй ещё: /r"
	sendMsg(bot, update, response)


def generateBattle(bot, update, args):
	logging.info(update)
	if not args:
		sendMsg(bot, update, "Живо передал параметры битвы в правильном формате!")
		return
	try:
		wordsLimit = int(args[0])
	except ValueError:
		sendMsg(bot, update, "Количество слов - число, блин.")
		return
	if wordsLimit == 1:
		sendMsg(bot, update, "Что, правда хочешь устроить бой из одного словца?! Какой-то ты неразумный.")
		return
	if len(args) < 2:
		weightsList = []
		sendMsg(bot, update, "Ты не передал веса слов! Будет полный хаос!!!")
	else:
		try:
			weightsList = [int(x) for x in args[1].split(",")]
		except ValueError:
			sendMsg(bot, update, "Если уж передаёшь веса, то передай их в правильном формате. Каждый вес - целое число")
			return
	battleArgs = [
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
	if len(args) > 2:
		try:
			params = parseStringArgs(args[2:], battleArgs)
		except ArgumentParserError as err:
			sendMsg(bot, update, "Какие-то ты кривые аргументы ввёл. Вот, почитай: %s\nПоддерживаемые аргументы:\n-e E - степень\n-m M - максимальный вес" % str(err))
			return
		if not params:
			sendMsg(bot, update, "Поддерживаемые аргументы:\n-e E - степень\n-m M - максимальный вес")
	response = game.generate(wordsLimit, weightsList, params)
	sendMsg(bot, update, response)


def getGameInfo(bot, update, args):
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


def getGameList(bot, update, args):
	limit = 10
	if args:
		try:
			limit = int(args[0])
		except ValueError:
			sendMsg(bot, update, "Количество игр - число, блин.")
			return
	logging.info(update)
	response = game.getList(limit)
	sendMsg(bot, update, response)


def setState(bot, update):
	logging.info(update)
	response = game.setPlayerState(update)
	sendMsg(bot, update, response)


def fight(bot, update):
	logging.info(update)
	response = game.start()
	sendMsg(bot, update, response)


def getGameResults(bot, update, args):
	logging.info(update)
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


def getCandidates(bot, update):
	logging.info(update)
	response = game.getCandidates(update)
	sendMsg(bot, update, response)


def vote(bot, update, args):
	logging.info(update)
	string = ' '.join(args).lower()
	if not string:
		response = """
			Ну ты чё. Скинь непустую строчку со своими баллами в формате: \"Словцо 1 Словцо 5 Словцо 2\".
			Где \"Словцо\" - название словца, а циферки - твои баллы.
		"""
	else:
		response = game.vote(update, string)
	sendMsg(bot, update, response)


def getMyVotes(bot, update):
	logging.info(update)
	response = game.getSelfVotes(update)
	sendMsg(bot, update, response)


def sendMsg(bot, update, msg):
	msg = re.sub(r"(?<=\n)[\s]+", "", msg) if msg else "Мне нечего тебе сказать, чёрт возьми!"
	bot.send_message(chat_id=update.message.chat_id, text=msg, parse_mode="html")

[
	dispatcher.add_handler(handler) for handler in [
		CommandHandler(['start', 'help', 'h', 'помощь'], start),
		CommandHandler(['gameinfo', 'gi', 'играинфо'], getGameInfo, pass_args=True),
		CommandHandler(['gamelist', 'gl', 'играсписок'], getGameList, pass_args=True),
		CommandHandler(['mywordsbygame', 'wg', 'моисловаигра'], showMyWordsPerGame, pass_args=True),
		CommandHandler(['mywordsbyround', 'wr', 'моисловараунд'], showMyWordsPerRound, pass_args=True),
		CommandHandler(['update', 'u', 'обновить', 'о'], updateMyWord, pass_args=True),
		CommandHandler(['random', 'r', 'случайное'], getRandomWord, pass_args=False),
		CommandHandler(['fight', 'f', 'битва', 'б'], fight, pass_args=False),
		CommandHandler(['candidates', 'c', 'к', 'кандидаты'], getCandidates, pass_args=False),
		CommandHandler(['ready', 'готов'], setState, pass_args=False),
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
