from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import logging
import traceback
from game.typeA import Game
from game.word import Word
import re

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)
updater = Updater(token='469542656:AAEIe3n3ir5oFpW1ce99u9EDk60tRzAC66Y')
dispatcher = updater.dispatcher
game = Game()


def start(bot, update):
	logging.info(update)
	sendMsg(bot, update, "Ну что ж, карапузы, готовте ваши словцы!")


def catchWord(bot, update):
	logging.info(update)
	try:
		response = game.addWord(update)
	except Exception as err:
		response = Game.ERROR_CODES['INNER_ERROR']
		# logging.critical("Exception: " + str(err), "Traceback: %s" % traceback.format_exc())
		raise
	sendMsg(bot, update, response)


def showMyWordsPerGame(bot, update, args):
	logging.info(update)
	game_id = int(args[0]) if args else None
	wordsList = game.getPlayerWordsByGame(game_id, update.message.chat.first_name)
	if not wordsList:
		response = "Какой стыд. Ты не смог предложить ни одного словца за всю игру!"
		sendMsg(bot, update, response)
		return
	response = """Вон они, твои словцы. Делай с ними теперь что хочешь:\n%s""" % " ".join(w['word'] for w in wordsList)
	sendMsg(bot, update, response)


def showMyWordsPerRound(bot, update, args):
	logging.info(update)
	round_id = int(args[0]) if args else None
	wordsList = game.getPlayerWordsByRound(round_id, update.message.chat.first_name)
	if not wordsList:
		response = "Какой стыд. Ты не смог предложить ни одного словца за целый раунд!"
		sendMsg(bot, update, response)
		return
	response = """Вон они, твои словцы. Делай с ними теперь что хочешь:\n%s""" % " ".join(w['word'] for w in wordsList)
	sendMsg(bot, update, response)


def updateMyWord(bot, update, args):
	logging.info(update)
	if len(args) != 2:
		response = "Слева - старое словоцо, справа - новое словцо. ДЕЛАЙ ТАК!"
		sendMsg(bot, update, response)
		return
	response = game.updateWord(args[0], args[1], update)
	sendMsg(bot, update, response)


def getRandomWord(bot, update):
	logging.info(update)
	word = game.getRandom('ushakov')
	if not word:
		response = "Очень странно. Не могу получить случайное словцо!"
	else:
		response = "Вот твоё случайное словцо: %s" % word.lower()
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
	""" % gameInfo
	sendMsg(bot, update, response)


def sendMsg(bot, update, msg):
	bot.send_message(chat_id=update.message.chat_id, text=msg)

[
	dispatcher.add_handler(handler) for handler in [
		CommandHandler('start', start),
		CommandHandler(['game_info', 'i', 'и'], getGameInfo, pass_args=True),
		CommandHandler(['my_words_by_game', 'wg', 'си'], showMyWordsPerGame, pass_args=True),
		CommandHandler(['my_words_by_round', 'wr', 'ср'], showMyWordsPerRound, pass_args=True),
		CommandHandler(['update', 'u', 'о'], updateMyWord, pass_args=True),
		CommandHandler(['get_random', 'gr', 'пс'], getRandomWord, pass_args=False),
		MessageHandler(Filters.text, catchWord)
	]
]
# dispatcher.add_handler(word_handler)
# dispatcher.add_handler(gameInfo_handler)
# dispatcher.add_handler(selfWordsByGame_handler)
# dispatcher.add_handler(selfWordsByRound_handler)
# dispatcher.add_handler(updateMyWord_handler)
# dispatcher.add_handler(word_handler)


if __name__ == "__main__":
	updater.start_polling()
