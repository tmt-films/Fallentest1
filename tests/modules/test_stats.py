import unittest
from unittest.mock import MagicMock, patch, call # call not used here but often useful
import html

# Assuming FallenRobot is in the Python path
from FallenRobot.modules import stats # For chat_stats_command
from FallenRobot.modules.sql import stats_sql # To patch its functions
# from FallenRobot.modules.helper_funcs import chat_status # For @user_admin if needed to mock its effect
# from FallenRobot import dispatcher # For ParseMode if not directly available in telegram module mock
from telegram import ParseMode, TelegramError # For ParseMode and TelegramError

class TestStatsCommand(unittest.TestCase):

    def setUp(self):
        self.update = MagicMock(spec=stats.Update) # stats.Update is telegram.Update
        self.context = MagicMock(spec=stats.CallbackContext)
        self.chat = MagicMock(spec=stats.telegram.Chat)
        self.user = MagicMock(spec=stats.telegram.User) # Admin user for tests
        self.bot = MagicMock(spec=stats.telegram.Bot)
        self.message = MagicMock(spec=stats.telegram.Message)

        self.update.effective_chat = self.chat
        self.update.effective_user = self.user
        self.update.effective_message = self.message
        self.context.bot = self.bot

        self.chat.id = "-1001234567890" # String, as used and converted in stats.py
        self.chat.title = "Awesome Test Group"
        self.user.id = 1 # Admin user

        self.message.reply_text = MagicMock() # Mock reply_text

        # Patch SQL functions used by stats.py
        self.patch_get_total = patch('FallenRobot.modules.sql.stats_sql.get_total_messages_in_chat')
        self.mock_get_total = self.patch_get_total.start()

        self.patch_get_unique_users = patch('FallenRobot.modules.sql.stats_sql.get_unique_users_count_in_chat')
        self.mock_get_unique_users = self.patch_get_unique_users.start()

        self.patch_get_top_posters = patch('FallenRobot.modules.sql.stats_sql.get_top_posters_in_chat')
        self.mock_get_top_posters = self.patch_get_top_posters.start()

        # Patch context.bot.get_chat_member
        self.patch_bot_get_chat_member = patch.object(self.context.bot, 'get_chat_member')
        self.mock_bot_get_chat_member = self.patch_bot_get_chat_member.start()

    def tearDown(self):
        self.patch_get_total.stop()
        self.patch_get_unique_users.stop()
        self.patch_get_top_posters.stop()
        self.patch_bot_get_chat_member.stop()

    def test_stats_command_data_available(self):
        self.mock_get_total.return_value = 1500
        self.mock_get_unique_users.return_value = 75
        top_posters_db_data = [(101, 100), (102, 80), (103, 70)]
        self.mock_get_top_posters.return_value = top_posters_db_data

        # Mock get_chat_member responses
        user101_member_mock = MagicMock()
        user101_member_mock.user.mention_html = MagicMock(return_value="<a href='tg://user?id=101'>Alice</a>")

        user102_member_mock = MagicMock()
        user102_member_mock.user.mention_html = MagicMock(return_value="<a href='tg://user?id=102'>Bob</a>")

        user103_member_mock = MagicMock()
        user103_member_mock.user.mention_html = MagicMock(return_value="<a href='tg://user?id=103'>Charlie</a>")

        self.mock_bot_get_chat_member.side_effect = [user101_member_mock, user102_member_mock, user103_member_mock]

        stats.chat_stats_command(self.update, self.context)

        expected_html = (
            f"📊 <b>Chat Statistics for {html.escape(self.chat.title)}</b>\n\n"
            f"💬 Total Logged Messages: 1500\n"
            f"👥 Unique Users Logged: 75\n\n"
            f"🏆 <b>Top Posters:</b>\n"
            f"  1. <a href='tg://user?id=101'>Alice</a> (100 messages)\n"
            f"  2. <a href='tg://user?id=102'>Bob</a> (80 messages)\n"
            f"  3. <a href='tg://user?id=103'>Charlie</a> (70 messages)\n"
        )
        self.message.reply_text.assert_called_once_with(expected_html, parse_mode=ParseMode.HTML)

    def test_stats_command_no_activity(self):
        self.mock_get_total.return_value = 0
        self.mock_get_unique_users.return_value = 0
        self.mock_get_top_posters.return_value = []

        stats.chat_stats_command(self.update, self.context)

        expected_html = (
            f"📊 <b>Chat Statistics for {html.escape(self.chat.title)}</b>\n\n"
            f"💬 Total Logged Messages: 0\n"
            f"👥 Unique Users Logged: 0\n\n"
            f"🏆 Top Posters: No activity logged yet or insufficient data.\n"
        )
        self.message.reply_text.assert_called_once_with(expected_html, parse_mode=ParseMode.HTML)

    def test_stats_command_top_posters_user_left_or_error(self):
        self.mock_get_total.return_value = 200
        self.mock_get_unique_users.return_value = 10
        top_posters_db_data = [(101, 50), (102, 40)]
        self.mock_get_top_posters.return_value = top_posters_db_data

        user101_member_mock = MagicMock()
        user101_member_mock.user.mention_html = MagicMock(return_value="<a href='tg://user?id=101'>Dave</a>")

        # Simulate TelegramError for user 102
        self.mock_bot_get_chat_member.side_effect = [user101_member_mock, TelegramError("User not found")]

        stats.chat_stats_command(self.update, self.context)

        expected_html = (
            f"📊 <b>Chat Statistics for {html.escape(self.chat.title)}</b>\n\n"
            f"💬 Total Logged Messages: 200\n"
            f"👥 Unique Users Logged: 10\n\n"
            f"🏆 <b>Top Posters:</b>\n"
            f"  1. <a href='tg://user?id=101'>Dave</a> (50 messages)\n"
            f"  2. User ID 102 (40 messages)\n"
        )
        self.message.reply_text.assert_called_once_with(expected_html, parse_mode=ParseMode.HTML)

    @patch('FallenRobot.modules.stats.LOGGER')
    def test_stats_command_sql_function_error(self, mock_logger):
        self.mock_get_total.side_effect = Exception("Simulated DB Error")
        self.mock_get_unique_users.return_value = 0
        self.mock_get_top_posters.return_value = []

        stats.chat_stats_command(self.update, self.context)

        self.message.reply_text.assert_called_once_with(
            "An error occurred while fetching chat statistics. Please try again later."
            # parse_mode is not specified in this reply in stats.py, so we don't assert it.
        )
        mock_logger.error.assert_called_once()
        self.assertIn("Error generating chat stats", mock_logger.error.call_args[0][0])
        self.assertIn("Simulated DB Error", str(mock_logger.error.call_args[1]['exc_info']))


if __name__ == '__main__':
    unittest.main()
```
