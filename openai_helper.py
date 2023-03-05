import logging
import openai
import time
CHAT_MODES = {
    "assistant": {
        "name": "Assistant",
        "welcome_message": "Hi, I'm <b>ChatGPT assistant</b>. How can I help you?",
        "prompt_start": "As an advanced chatbot named ChatGPT, your primary goal is to assist users to the best of your ability. This may involve answering questions, providing helpful information, or completing tasks based on user input. In order to effectively assist users, it is important to be detailed and thorough in your responses. Use examples and evidence to support your points and justify your recommendations or solutions. Remember to always prioritize the needs and satisfaction of the user. Your ultimate goal is to provide a helpful and enjoyable experience for the user."
    },

    "code_assistant": {
        "name": "Code Assistant",
        "welcome_message": "👩🏼‍💻 Hi, I'm <b>ChatGPT code assistant</b>. How can I help you?",
        "prompt_start": "As an advanced chatbot named ChatGPT, your primary goal is to assist users to write code. This may involve designing/writing/editing/describing code or providing helpful information. Where possible you should provide code examples to support your points and justify your recommendations or solutions. Make sure the code you provide is correct and can be run without errors. Be detailed and thorough in your responses. Your ultimate goal is to provide a helpful and enjoyable experience for the user. Write code inside <code>, </code> tags."
    },

    "text_improver": {
        "name": "Text Improver",
        "welcome_message": "📝 Hi, I'm <b>ChatGPT text improver</b>. Send me any text – I'll improve it and correct all the mistakes",
        "prompt_start": "As an advanced chatbot named ChatGPT, your primary goal is to correct spelling, fix mistakes and improve text sent by user. Your goal is to edit text, but not to change it's meaning. You can replace simplified A0-level words and sentences with more beautiful and elegant, upper level words and sentences. All your answers strictly follows the structure (keep html tags):\n<b>Edited text:</b>\n{EDITED TEXT}\n\n<b>Correction:</b>\n{NUMBERED LIST OF CORRECTIONS}"
    },

    "translator" : {
        "name": "Translator",
        "welcome_message" : "Starting translate mode.",
        "prompt_start": "translate input to output"
    }
}



class OpenaiHelper:
    '''
    Image and NLP helper class
    '''

    def __init__(self, config: dict):
        openai.api_key = config['api_key']
        openai.proxy = config['proxy']
        self.config = config
        self.sessions: dict[int: list] = dict()


    def get_answers(self, message, chat_id, chat_mode='assistant'):

        if chat_id not in self.sessions:
            self.reset_chat_history(chat_id, chat_mode)

        if chat_mode not in CHAT_MODES.keys():
            raise ValueError(f"Chat mode {chat_mode} is not supported")

        answer = None
        retry_count = 0
        while answer is None:

            logging.info(f'retry count: {retry_count}')
            retry_count += 1
            try:
                messages = self._generate_prompt_msg(message, chat_id, chat_mode)

                res = openai.ChatCompletion.create(
                    model=self.config['model'],
                    messages=messages,
                    temperature=self.config['temperature'],
                    max_tokens=self.config['max_tokens'],
                    presence_penalty=self.config['presence_penalty'],
                    frequency_penalty=self.config['frequency_penalty'],
                )
                if len(res) > 0:
                    answer = ''
                    answer = res.choices[0].message["content"]
                    logging.info(f'answer: {answer}')
                else:
                    logging.error('No response from GPT-3')
                    return "⚠️ _An error has occurred_ ⚠️\nPlease try again in a while."

            except openai.error.InvalidRequestError as e:
                # too many tokens
                if len(self.sessions[chat_id]) == 0:
                    raise ValueError("Message too long, reduce input message and try again") from e
                # forget the earliest message
                self.sessions[chat_id] = self.sessions[chat_id][1:]
                time.sleep(2)
            except openai.error.RateLimitError as e:
                logging.exception(e)
                return f"⚠️ _OpenAI Rate Limit exceeded_ ⚠️\n{str(e)}"
            except Exception as e:
                logging.exception(e)
                return f"⚠️ _An error has occurred_ ⚠️\n{str(e)}"


        self._add_to_history(chat_id, role="user", content=message)
        self._add_to_history(chat_id, role="assistant", content=answer)
        logging.info(f'dialog: {self.sessions[chat_id]}')
        answer = self._postprocess_answer(answer, res)
        return answer


    def _generate_prompt_msg(self, message, chat_id, chat_mode='assistant'):
        messages = self.sessions[chat_id].copy()
        logging.info(f'previous messages: {messages}')
        messages.append({
            "role": "user",
            "content": message
        })

        logging.info(f'final messages: {messages}')
        return messages

    def _postprocess_answer(self, answer, response):
        answer = answer.strip()
        if self.config["show_usage"]:
            answer += "\n\n---\n" \
                      f"💰 Tokens used: {str(response.usage['total_tokens'])}" \
                      f" ({str(response.usage['prompt_tokens'])} prompt," \
                      f" {str(response.usage['completion_tokens'])} completion)"

        return answer

    def generate_image(self, prompt: str) -> str:
        """
        Generates an image from the given prompt using DALL·E model.
        :param prompt: The prompt to send to the model
        :return: The image URL
        """
        try:
            response = openai.Image.create(
                prompt=prompt,
                n=1,
                size=self.config['image_size']
            )
            return response['data'][0]['url']

        except Exception as e:
            logging.exception(e)
            raise e

    def reset_chat_history(self, chat_id, chat_mode='assistant'):
        """
        Resets the conversation history.
        """

        prompt = self.config['assistant_prompt']
        logging.info(prompt)
        self.sessions[chat_id] = [{"role": "system", "content": prompt}]
        logging.info(f'reset prompt: {self.sessions[chat_id]}')

    def _add_to_history(self, chat_id, role, content):
        """
        Adds a message to the conversation history.
        :param chat_id: The chat ID
        :param role: The role of the message sender
        :param content: The message content
        """
        self.sessions[chat_id].append({"role": role, "content": content})
