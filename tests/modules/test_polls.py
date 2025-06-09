import unittest
from unittest.mock import MagicMock, patch
import html # For escaping in expected replies if needed

from FallenRobot.modules import polls # Assuming FallenRobot is in path
import telegram # For ParseMode, TelegramError etc.

class TestPollsModule(unittest.TestCase):

    def setUp(self):
        self.update = MagicMock(spec=telegram.Update)
        self.context = MagicMock(spec=polls.CallbackContext) # polls.CallbackContext is fine
        self.chat = MagicMock(spec=telegram.Chat)
        self.message = MagicMock(spec=telegram.Message)
        self.bot = MagicMock(spec=telegram.Bot)

        self.update.effective_chat = self.chat
        self.update.effective_message = self.message
        self.context.bot = self.bot

        self.chat.id = 12345
        self.message.text = "" # Will be set per test
        self.message.reply_text = MagicMock() # Mock reply_text directly on message instance

    # No tearDown needed if only patching context.bot.send_poll per call for most tests

    def test_create_poll_success(self):
        self.message.text = '/poll "Favorite color?" "Red" "Blue" "Green"'
        with patch.object(self.context.bot, 'send_poll') as mock_send_poll:
            polls.poll_command(self.update, self.context)
            mock_send_poll.assert_called_once_with(
                chat_id=self.chat.id,
                question="Favorite color?",
                options=["Red", "Blue", "Green"],
                is_anonymous=True
            )
        self.message.reply_text.assert_not_called()

    def test_create_poll_no_args(self):
        self.message.text = '/poll'
        polls.poll_command(self.update, self.context)
        expected_html_msg = (
            "<b>Please provide a question and options for the poll.</b>\n\n"
            "<b>Usage:</b> <code>/poll \"Your Question\" \"Option 1\" \"Option 2\" \"Option 3\" ...</code>\n"
            "You need at least one question and two options.\n"
            "Options must be between 1 and 100 characters. Question between 1 and 300."
        )
        self.message.reply_text.assert_called_with(expected_html_msg, parse_mode=telegram.ParseMode.HTML)

    def test_create_poll_only_question(self):
        self.message.text = '/poll "What is your name?"'
        polls.poll_command(self.update, self.context)
        self.message.reply_text.assert_called_with("You need to provide at least two options for the poll.")

    def test_create_poll_one_option(self):
        self.message.text = '/poll "What is your name?" "Arthur"'
        polls.poll_command(self.update, self.context)
        self.message.reply_text.assert_called_with("You need to provide at least two options for the poll.")

    def test_create_poll_too_many_options(self):
        options_list = [f'"Opt{i}"' for i in range(11)] # 11 options
        options_str = " ".join(options_list)
        self.message.text = f'/poll "Too many?" {options_str}'
        polls.poll_command(self.update, self.context)
        self.message.reply_text.assert_called_with("You can provide a maximum of 10 options for the poll.")

    def test_create_poll_question_too_long(self):
        long_question = "Q" * 301
        self.message.text = f'/poll "{long_question}" "Opt1" "Opt2"'
        polls.poll_command(self.update, self.context)
        self.message.reply_text.assert_called_with("Poll question is too long. Maximum 300 characters.")

    def test_create_poll_option_too_long(self):
        long_option = "O" * 101
        short_option_display = "O" * 50 # As per current polls.py error message
        self.message.text = f'/poll "Valid Q" "Opt1" "{long_option}"'
        polls.poll_command(self.update, self.context)
        self.message.reply_text.assert_called_with(
            f"Option '{short_option_display}...' is too long. Maximum 100 characters per option."
        )

    def test_create_poll_empty_question_after_parse(self):
        self.message.text = '/poll "" "Opt1" "Opt2"'
        polls.poll_command(self.update, self.context)
        self.message.reply_text.assert_called_with("Poll question cannot be empty.")

    def test_create_poll_empty_option_after_parse(self):
        self.message.text = '/poll "Valid Q" "" "Opt2"'
        polls.poll_command(self.update, self.context)
        self.message.reply_text.assert_called_with("Poll options cannot be empty.")

    def test_create_poll_shlex_parse_error(self):
        error_message = "Simulated shlex error"
        self.message.text = '/poll "Unclosed quote "Opt1" "Opt2"'
        with patch('FallenRobot.modules.polls.shlex.split', side_effect=ValueError(error_message)):
            polls.poll_command(self.update, self.context)
            self.message.reply_text.assert_called_with(
                f"Error parsing arguments: {error_message}. Ensure quotes are properly matched."
            )

    def test_create_poll_telegram_error_on_send(self):
        error_message = "Simulated API error"
        self.message.text = '/poll "Good Poll" "Yes" "No"'
        with patch.object(self.context.bot, 'send_poll', side_effect=telegram.TelegramError(error_message)) as mock_send_poll:
            polls.poll_command(self.update, self.context)
            mock_send_poll.assert_called_once()
            self.message.reply_text.assert_called_with(f"An error occurred while sending the poll: {error_message}")

if __name__ == '__main__':
    unittest.main()
```
