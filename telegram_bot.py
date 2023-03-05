import logging
import openai_helper
from telegram import (
    Update,
    User,
    InlineKeyboardButton,
    InlineKeyboardMarkup)

from telegram.ext import (
    ApplicationBuilder,
    CallbackContext,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
from telegram.constants import ParseMode, ChatAction
import telegram.constants as constants
import telegram
from functools import partial, wraps

HELP_MESSAGE = """Commands:
• /reset – Reset conversation
• /image <prompt> - Generate image
• /mode – Select chat mode
• /balance – Show balance
• /help – Help menu
"""

class restricted(object):
    """
    Decorator class used to restrict usage of commands.
    Sends a "disallowed" reply if necessary. Works on functions and methods.
    """
    def __init__(self, func):
        self._func = func
        self._obj = None
        self._wrapped = None

    def __call__(self, *args, **kwargs):
        if not self._wrapped:
            if self._obj:
                self._wrapped = self._wrap_method(self._func)
                self._wrapped = partial(self._wrapped, self._obj)
            else:
                self._wrapped = self._wrap_function(self._func)
        return self._wrapped(*args, **kwargs)

    def __get__(self, obj, type_=None):
        self._obj = obj
        return self

    def _wrap_method(self, method): # Wrapper called in case of a method
        @wraps(method)
        async def inner(self, *args, **kwargs): # `self` is the *inner* class' `self` here
            user_id = args[0].effective_user.id # args[0]: update
            if self.config['allowed_user_ids'] != '*':
                if str(user_id) not in self.config['allowed_user_ids'].split(','):
                    logging.info(f'Unauthorized access denied on {method.__name__} ' \
                                 f'for {user_id} : {args[0].message.chat.username}.')
                    await args[0].message.reply_text('Sorry, you are not allowed to use this bot.')
                    return None # quit handling command
            return await method(self, *args, **kwargs)
        return inner

    def _wrap_function(self, function): # Wrapper called in case of a function
        @wraps(function)
        async def inner(*args, **kwargs): # `self` would be the *restricted* class' `self` here
            user_id = args[0].effective_user.id # args[0]: update
            if self.config['allowed_user_ids'] != '*':
                if str(user_id) not in self.config['allowed_user_ids'].split(','):
                    logging.info(f'Unauthorized access denied on {function.__name__} ' \
                        f'for {user_id} : {args[0].message.chat.username}.')
                    await args[0].message.reply_text('Sorry, you are not allowed to use this bot.')
                    return None # quit handling command
            return await function(*args, **kwargs)
        return inner

class TelegramBot:
    def __init__(self, config, openai):
        '''
        Init
        :param config:  token, proxy and others
        '''
        self.config = config
        self.openai = openai
        self.modes: dict[int: str] = dict()  # use_id: chat_mode


    @restricted
    async def start(self, update: Update, context: CallbackContext):

        logging.info(f'trigger start command')
        reply_text = "Hi! I'm *ChatGPT* bot \n\n"
        reply_text += HELP_MESSAGE
        reply_text += "\nask me anything!"

        await update.message.reply_markdown(reply_text)

    @restricted
    async def help(self, update: Update, context: CallbackContext):
        '''
        Show help menu.
        :param update:
        :param context:
        :return: None
        '''
        logging.info(f'trigger help command')

        await update.message.reply_markdown(HELP_MESSAGE)


    @restricted
    async def image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        '''
        Generate an image for the given prompt using DALL-E
        :param update:
        :param context:
        :return: image
        '''
        logging.info("New message form user")
        chat_id = update.effective_chat.id
        img_prompt = update.message.text.replace('/image', '').strip()
        if img_prompt == '':
            await context.bot.send_message(chat_id=chat_id, text='Please provide a prompt')
            return
        await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.UPLOAD_PHOTO)
        try:
            img_url = self.openai.generate_image(prompt=img_prompt)
            await context.bot.send_photo(
                chat_id=chat_id,
                reply_to_message_id=update.message.message_id,
                photo=img_url
            )
        except:
            await context.bot.send_message(
                chat_id=chat_id,
                reply_to_message_id=update.message.message_id,
                text="Failed to generate image, please try again"
            )

    @restricted
    async def send_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        '''
        Send message to chatGPT
        :param update:
        :param context:
        :return: answer
        '''
        logging.info(f'New message from user')
        chat_id = update.effective_chat.id

        await update.message.chat.send_action(action="typing")

        answer = self.openai.get_answers(message=update.message.text, chat_id=chat_id)
        logging.info(f'sending message.')
        await update.message.chat.send_action(action="typing")

        try:
            await update.message.reply_text(answer, parse_mode=ParseMode.MARKDOWN_V2)
        except telegram.error.BadRequest:
            # answer has invalid characters, so we send it without parse_mode
            await update.message.reply_text(answer)

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        '''
        Handels error
        :param update:
        :param context:
        :return: None
        '''
        logging.debug(f'Exception while handling an update: {context.error}')

    @restricted
    async def show_chat_modes_handle(self, update: Update, context: CallbackContext):
        logging.info(f'trigger modes command')

        keyboard = []
        for chat_mode, chat_mode_dict in openai_helper.CHAT_MODES.items():
            keyboard.append([InlineKeyboardButton(chat_mode_dict["name"], callback_data=f"set_chat_mode|{chat_mode}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        logging.info(f'reply_markup ： {reply_markup}')
        await update.message.reply_text("Select chat mode:", reply_markup=reply_markup)

    @restricted
    async def set_chat_mode_handle(self, update: Update, context: CallbackContext):
        user_id = update.callback_query.from_user.id

        query = update.callback_query
        await query.answer()

        chat_mode = query.data.split("|")[1]

        self.modes[user_id] = chat_mode

        await query.edit_message_text(
            f"<b>{openai_helper.CHAT_MODES[chat_mode]['name']}</b> chat mode is set",
            parse_mode=ParseMode.HTML
        )

        await query.edit_message_text(f"{openai_helper.CHAT_MODES[chat_mode]['welcome_message']}",
                                      parse_mode=ParseMode.HTML)

    @restricted
    async def reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Resets the conversation.
        """

        logging.info(f'resetting the conversation')
        chat_id = update.effective_chat.id
        self.openai.reset_chat_history(chat_id=chat_id)
        await update.message.reply_text('done!')



    def run(self):
        """
        Runs the bot indefinitely
        """

        application = ApplicationBuilder() \
            .token(self.config['token']) \
            .proxy_url(self.config['proxy']) \
            .get_updates_proxy_url(self.config['proxy']) \
            .build()

        application.add_handler(CommandHandler('reset', self.reset))
        application.add_handler(CommandHandler('help', self.help))
        application.add_handler(CommandHandler('image', self.image))
        application.add_handler(CommandHandler('start', self.start))
        application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.send_message))
        application.add_handler(CommandHandler("mode", self.show_chat_modes_handle))
        application.add_handler(CallbackQueryHandler(self.set_chat_mode_handle, pattern="^set_chat_mode"))

        application.add_error_handler(self.error_handler)

        application.run_polling()

