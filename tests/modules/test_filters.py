import unittest
from unittest.mock import MagicMock, patch, call
import html # For escaping in expected replies

from FallenRobot.modules import filters # Assuming FallenRobot is in path
from FallenRobot.modules.sql import filters_sql # For type hinting if needed, and for patching
import telegram # For ParseMode and other telegram types

class TestFiltersModule(unittest.TestCase):

    def setUp(self):
        self.update = MagicMock(spec=telegram.Update)
        self.context = MagicMock(spec=filters.CallbackContext) # Using filters.CallbackContext is fine
        self.chat = MagicMock(spec=telegram.Chat)
        self.user = MagicMock(spec=telegram.User) # Admin user
        self.non_admin_user = MagicMock(spec=telegram.User)
        self.bot = MagicMock(spec=telegram.Bot)
        self.message = MagicMock(spec=telegram.Message)

        self.update.effective_chat = self.chat
        self.update.effective_user = self.user
        self.update.effective_message = self.message
        self.context.bot = self.bot
        self.context.args = []

        self.chat.id = 12345
        self.chat.title = "Test Chat" # For loggable if it uses chat title
        self.user.id = 1
        self.user.first_name = "AdminUser" # For loggable
        self.user.mention_html = MagicMock(return_value=f"<a href='tg://user?id={self.user.id}'>{self.user.first_name}</a>")
        self.non_admin_user.id = 2
        self.non_admin_user.first_name = "NonAdmin"

        # Patch SQL functions
        self.patch_add_filter = patch('FallenRobot.modules.sql.filters_sql.add_filter')
        self.mock_add_filter = self.patch_add_filter.start()

        self.patch_remove_filter = patch('FallenRobot.modules.sql.filters_sql.remove_filter')
        self.mock_remove_filter = self.patch_remove_filter.start()

        self.patch_get_chat_filters = patch('FallenRobot.modules.sql.filters_sql.get_chat_filters')
        self.mock_get_chat_filters = self.patch_get_chat_filters.start()

        # Patch helper functions
        self.patch_is_user_admin = patch('FallenRobot.modules.filters.is_user_admin')
        self.mock_is_user_admin = self.patch_is_user_admin.start()

        self.patch_bot_can_delete = patch('FallenRobot.modules.filters.bot_can_delete_messages')
        self.mock_bot_can_delete = self.patch_bot_can_delete.start()

    def tearDown(self):
        self.patch_add_filter.stop()
        self.patch_remove_filter.stop()
        self.patch_get_chat_filters.stop()
        self.patch_is_user_admin.stop()
        self.patch_bot_can_delete.stop()

    # Test /addfilter
    def test_add_filter_success(self):
        # self.mock_is_user_admin is implicitly True due to @user_admin_no_reply
        # For direct command testing, we assume the decorator allowed the call.
        # If @user_admin_no_reply itself sends a message when user is not admin,
        # then we'd need a different test for that specific decorator's behavior.
        # Here, we test the command logic assuming admin access.
        self.context.args = ["badword"]
        filters.add_filter_cmd(self.update, self.context)
        self.mock_add_filter.assert_called_once_with(self.chat.id, "badword")
        self.message.reply_text.assert_called_with(
            f"Added filter for '<code>{html.escape('badword')}</code>'.", # Match HTML output
            parse_mode=telegram.ParseMode.HTML
        )

    def test_add_filter_no_keyword(self):
        self.context.args = []
        filters.add_filter_cmd(self.update, self.context)
        self.message.reply_text.assert_called_with("Please specify a keyword to filter!")
        self.mock_add_filter.assert_not_called()

    def test_add_filter_long_keyword(self):
        self.context.args = ["a"*101]
        filters.add_filter_cmd(self.update, self.context)
        self.message.reply_text.assert_called_with("Filter keyword is too long. Keep it under 100 characters.")
        self.mock_add_filter.assert_not_called()

    # Test /rmfilter
    def test_rm_filter_success(self):
        self.context.args = ["badword"]
        self.mock_remove_filter.return_value = True
        filters.rm_filter_cmd(self.update, self.context)
        self.mock_remove_filter.assert_called_once_with(self.chat.id, "badword")
        self.message.reply_text.assert_called_with(
            f"Removed filter for '<code>{html.escape('badword')}</code>'.", # Match HTML output
            parse_mode=telegram.ParseMode.HTML
        )

    def test_rm_filter_not_found(self):
        self.context.args = ["badword"]
        self.mock_remove_filter.return_value = False
        filters.rm_filter_cmd(self.update, self.context)
        self.mock_remove_filter.assert_called_once_with(self.chat.id, "badword")
        self.message.reply_text.assert_called_with("This filter doesn't exist or was already removed.")

    def test_rm_filter_no_keyword(self):
        self.context.args = []
        filters.rm_filter_cmd(self.update, self.context)
        self.message.reply_text.assert_called_with("Please specify a keyword to remove!")
        self.mock_remove_filter.assert_not_called()


    # Test /filters (listfilters)
    def test_list_filters_found(self):
        keywords = ["badword", "another"]
        self.mock_get_chat_filters.return_value = [(k,) for k in keywords]
        filters.list_filters_cmd(self.update, self.context)

        expected_reply = "<b>Active filters in this chat:</b>\n"
        for keyword in keywords:
            expected_reply += f"- <code>{html.escape(keyword)}</code>\n"

        self.message.reply_text.assert_called_with(expected_reply, parse_mode=telegram.ParseMode.HTML)

    def test_list_filters_none(self):
        self.mock_get_chat_filters.return_value = []
        filters.list_filters_cmd(self.update, self.context)
        self.message.reply_text.assert_called_with("No filters are active in this chat.")

    # Test Message Handler
    def test_filter_message_handler_deletes_message(self):
        self.message.text = "This is a badword message."
        self.update.effective_user = self.non_admin_user # Message from non-admin
        self.mock_get_chat_filters.return_value = [("badword",)]
        self.mock_is_user_admin.return_value = False # Sender is not admin
        self.mock_bot_can_delete.return_value = True

        filters.filter_message_handler(self.update, self.context)
        self.message.delete.assert_called_once()

    def test_filter_message_handler_case_insensitive(self):
        self.message.text = "This is a BADWORD message."
        self.update.effective_user = self.non_admin_user
        self.mock_get_chat_filters.return_value = [("badword",)]
        self.mock_is_user_admin.return_value = False
        self.mock_bot_can_delete.return_value = True

        filters.filter_message_handler(self.update, self.context)
        self.message.delete.assert_called_once()

    def test_filter_message_handler_no_match(self):
        self.message.text = "This is a clean message."
        self.update.effective_user = self.non_admin_user
        self.mock_get_chat_filters.return_value = [("badword",)]
        self.mock_is_user_admin.return_value = False # Not strictly needed here, but good for consistency

        filters.filter_message_handler(self.update, self.context)
        self.message.delete.assert_not_called()

    def test_filter_message_handler_admin_exempt(self):
        self.message.text = "Admin says badword."
        self.update.effective_user = self.user # Message from admin
        self.mock_get_chat_filters.return_value = [("badword",)]
        self.mock_is_user_admin.return_value = True # Sender is admin

        filters.filter_message_handler(self.update, self.context)
        self.message.delete.assert_not_called()

    def test_filter_message_handler_bot_cannot_delete(self):
        self.message.text = "This is a badword message."
        self.update.effective_user = self.non_admin_user
        self.mock_get_chat_filters.return_value = [("badword",)]
        self.mock_is_user_admin.return_value = False
        self.mock_bot_can_delete.return_value = False

        filters.filter_message_handler(self.update, self.context)
        self.message.delete.assert_not_called()

    def test_filter_message_handler_no_text(self):
        self.message.text = None # Sticker, photo etc.
        self.update.effective_user = self.non_admin_user
        self.mock_get_chat_filters.return_value = [("badword",)]

        filters.filter_message_handler(self.update, self.context)
        self.message.delete.assert_not_called()

    def test_filter_message_handler_no_filters_in_chat(self):
        self.message.text = "This is a badword message."
        self.update.effective_user = self.non_admin_user
        self.mock_get_chat_filters.return_value = [] # No filters set for the chat

        filters.filter_message_handler(self.update, self.context)
        self.message.delete.assert_not_called()


if __name__ == '__main__':
    unittest.main()
```
