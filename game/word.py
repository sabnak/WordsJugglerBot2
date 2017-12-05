from libs.dbAdapter import DB
import re


class Word:

	ERROR_CODES = {
		"TOO_SHORT_WORD": "Ха! Вы только посмотрите! Какое маленькое, жалкое и скукоженное словцо! Минимальная длина словца - %d букв.",
		"INVALID_WORD": "Это не похоже на словцо! Не похоже! Словцо должно содержать только русские буквы, невежа.",
		"NOT_IN_TIME_WORD": "Ну ты и проныра! Ты уже втюхнул максимальное количество (%d) своих жалких словцов в этом раунде!",
		"EXISTED_WORD_NEW": "Ах ты ж маленькая слабоумная сковорода. Такое словцо уже предлагали!",
		"EMPTY_WORD": "Словцо-то введи, горемыка."
	}

	@staticmethod
	def add(wordsLimit, wordMinLength, **params):
		params['word'] = params['word'].strip().lower()
		wordsForToday = DB.getList("""
			SELECT *
			FROM word
			WHERE player_id = %(player_id)s AND game_id = %(game_id)s AND round_id = %(round_id)s
		""", params)
		if len(wordsForToday) >= wordsLimit:
			return False, Word.ERROR_CODES['NOT_IN_TIME_WORD'] % wordsLimit
		status, response = Word.isWordValid(params['word'], wordMinLength)
		if not status:
			return False, response
		DB.execute("INSERT INTO word SET word = %(word)s, player_id = %(player_id)s, game_id = %(game_id)s, round_id = %(round_id)s", params)
		wordsForToday = DB.getList("SELECT * FROM word WHERE player_id = %(player_id)s AND game_id = %(game_id)s AND round_id = %(round_id)s", params)
		additionalMsg = ""
		if len(wordsForToday) == wordsLimit:
			additionalMsg = " У тебя больше не осталось словцов в этом раунде, растяпа!"
		if len(wordsForToday) < wordsLimit:
			additionalMsg = " Ты можешь предложить ещё %d смешных словца" % (wordsLimit - len(wordsForToday))
		return True, "Твоё жалкое словцо \"%s\" принято, свинюшка! %s" % (params['word'], additionalMsg)

	@staticmethod
	def getIdByName(**params):
		word = DB.getOne("SELECT id FROM word WHERE word = %(word)s AND word.round_id = %(round_id)s AND word.game_id = %(game_id)s", params)
		return word['id'] if word else None

	@staticmethod
	def getListByGameId(game_id, player_id=None, fullAccess=False):
		condition = "word.player_id = %(player_id)s" if player_id else "round.status = 'ended'" if not fullAccess else ""
		return DB.getList("""
		SELECT word.*, round.number
		FROM word
		JOIN round ON (round.id = word.round_id)
		WHERE word.game_id = %(game_id)s AND
		""" + condition, dict(game_id=game_id, player_id=player_id))

	@staticmethod
	def getListByRoundId(fullAccess=False, **params):
		condition = " AND word.player_id = %(player_id)s" if 'player_id' in params else " AND player.telegram_id = %(telegram_id)s" if 'telegram_id' in params else " AND round.status = 'ended'" if not fullAccess else ""
		return DB.getList("""
		SELECT word.*, player.name, player.telegram_id, round.number
		FROM word
		JOIN round ON (round.id = word.round_id)
		JOIN player ON (player.id = word.player_id)
		WHERE word.round_id = %(round_id)s
		""" + condition, params)

	@staticmethod
	def getListByGroupNumber(**params):
		return DB.getList("""
		SELECT word.*, player.name, player.telegram_id, round.number
		FROM word
		JOIN round ON (round.id = word.round_id)
		JOIN player ON (player.id = word.player_id)
		JOIN groups ON (groups.word_id = word.id AND groups.round_id = %(round_id)s AND groups.number = %(groupNumber)s)
		WHERE word.round_id = %(round_id)s
		""", params)

	@staticmethod
	def update(wordMinLength, **params):
		params['oldWord'] = params['oldWord'].lower()
		params['newWord'] = params['newWord'].lower()
		if params['newWord'] == params['oldWord']:
			return "И ты прислал два одинаковых слова... Зачем ты так глуп, а?"
		oldWord = DB.getOne("""
			SELECT *
			FROM word
			WHERE word = %(oldWord)s AND player_id = %(player_id)s AND round_id = %(round_id)s AND game_id = %(game_id)s
		""", params)
		if not oldWord:
			return "У тебя нет такого словца в последнем раунде или он уже завершён, дурында!"
		status, response = Word.isWordValid(word=params['newWord'], wordMinLength=wordMinLength)
		if not status:
			return response
		affectedRows = DB.execute("""
			UPDATE word
			SET word = '%s'
			WHERE id = %d""" % (params['newWord'], oldWord['id'])).rowcount
		return "Хм... Я не смог обновить словцо. Интересно почему?" if not affectedRows else "Словцо успешно обновлено. Надеюсь, оно было получше прежнего"

	@staticmethod
	def isWordValid(word, wordMinLength):
		errorMsg = None
		if not word:
			errorMsg = Word.ERROR_CODES['EMPTY_WORD']
		elif Word._isWordExist(word):
			errorMsg = Word.ERROR_CODES['EXISTED_WORD_NEW']
		elif not re.match(r"^[А-яё]+$", word):
			errorMsg = Word.ERROR_CODES['INVALID_WORD']
		elif len(word) < wordMinLength:
			errorMsg = Word.ERROR_CODES['TOO_SHORT_WORD'] % wordMinLength
		if errorMsg:
			return False, errorMsg
		return True, None

	@staticmethod
	def isWordBelongToPlayer(**params):
		return True if DB.getOne("SELECT * FROM word WHERE round_id = %(round_id)s AND word = %(word)s AND player_id = %(player_id)s", params) else False

	@staticmethod
	def _isWordExist(word):
		return True if DB.getOne("SELECT * FROM word WHERE word = %(word)s ORDER BY createDate DESC LIMIT 1", dict(word=word)) else False

