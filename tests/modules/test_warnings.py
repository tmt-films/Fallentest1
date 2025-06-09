import unittest
from unittest.mock import MagicMock, patch, call

# Assuming FallenRobot is in the Python path for testing
# Adjust imports based on actual project structure if needed for standalone test execution
from FallenRobot.modules import warnings # This will import the module
from FallenRobot.modules.sql import warns_sql # This is also needed if directly used or for patching
import telegram # Import telegram for type hinting and ParseMode if not directly from warnings

class TestWarningsModule(unittest.TestCase):

    def setUp(self):
        # Mock common Telegram objects
        self.update = MagicMock(spec=telegram.Update) # Use telegram.Update
        self.context = MagicMock(spec=warnings.CallbackContext)
        self.chat = MagicMock(spec=telegram.Chat) # Use telegram.Chat
        self.user = MagicMock(spec=telegram.User) # Admin user # Use telegram.User
        self.target_user_mock = MagicMock(spec=telegram.User) # User being warned, distinct from self.user
        self.bot = MagicMock(spec=telegram.Bot) # Use telegram.Bot

        self.update.effective_chat = self.chat
        self.update.effective_user = self.user
        self.update.effective_message = MagicMock(spec=telegram.Message) # Use telegram.Message
        self.context.bot = self.bot
        self.context.args = []

        self.chat.id = 12345
        self.chat.title = "Test Chat"
        self.user.id = 1
        self.user.first_name = "Admin"
        self.user.mention_html = MagicMock(return_value="<a href='tg://user?id=1'>Admin</a>")

        self.target_user_mock.id = 2
        self.target_user_mock.first_name = "Target"
        # Mock the .user attribute for when chat.get_member(target_user_id).user is called
        self.target_user_member_mock = MagicMock()
        self.target_user_member_mock.user = self.target_user_mock
        self.target_user_mock.mention_html = MagicMock(return_value=f"<a href='tg://user?id={self.target_user_mock.id}'>{self.target_user_mock.first_name}</a>")


        self.bot.id = 1000

        # Mock chat.get_member to return the appropriate user mock
        self.chat.get_member = MagicMock()
        # Default behavior: bot is admin, target user is regular user
        def side_effect_get_member(user_id):
            if user_id == self.target_user_mock.id:
                return self.target_user_member_mock
            elif user_id == self.bot.id:
                bot_member_mock = MagicMock()
                bot_member_mock.is_administrator = True # For bot admin check in tagall (not here)
                bot_member_mock.can_restrict_members = True # For kick check
                return bot_member_mock
            elif user_id == self.user.id: # Admin user performing action
                admin_member_mock = MagicMock()
                admin_member_mock.user = self.user
                return admin_member_mock
            return MagicMock() # Default mock for other IDs
        self.chat.get_member.side_effect = side_effect_get_member

        # Patch the SQL functions used by the warnings module
        self.patch_warn_user = patch('FallenRobot.modules.sql.warns_sql.warn_user')
        self.mock_warn_user = self.patch_warn_user.start()

        self.patch_get_warns = patch('FallenRobot.modules.sql.warns_sql.get_warns')
        self.mock_get_warns = self.patch_get_warns.start()

        self.patch_reset_warns = patch('FallenRobot.modules.sql.warns_sql.reset_warns')
        self.mock_reset_warns = self.patch_reset_warns.start()

        self.patch_get_warn_setting = patch('FallenRobot.modules.sql.warns_sql.get_warn_setting')
        self.mock_get_warn_setting = self.patch_get_warn_setting.start()

        self.patch_set_warn_limit = patch('FallenRobot.modules.sql.warns_sql.set_warn_limit')
        self.mock_set_warn_limit = self.patch_set_warn_limit.start()

        self.patch_set_warn_strength = patch('FallenRobot.modules.sql.warns_sql.set_warn_strength')
        self.mock_set_warn_strength = self.patch_set_warn_strength.start()

        # Patch helper functions
        # Note: warnings.is_user_admin should be FallenRobot.modules.warnings.is_user_admin if that's its full path
        self.patch_is_user_admin = patch('FallenRobot.modules.warnings.is_user_admin')
        self.mock_is_user_admin = self.patch_is_user_admin.start()

        self.patch_user_can_warn = patch('FallenRobot.modules.warnings.user_can_warn')
        self.mock_user_can_warn = self.patch_user_can_warn.start()

        self.patch_extract_user_and_text = patch('FallenRobot.modules.warnings.extract_user_and_text')
        self.mock_extract_user_and_text = self.patch_extract_user_and_text.start()

        # This was bot_can_delete_messages in the provided test, but warnings.py uses
        # chat.get_member(context.bot.id).can_restrict_members for kick.
        # The self.chat.get_member mock now covers this.
        # If there's a separate bot_can_kick or bot_can_delete_messages helper, it should be patched.
        # For now, relying on the chat.get_member mock.

    def tearDown(self):
        self.patch_warn_user.stop()
        self.patch_get_warns.stop()
        self.patch_reset_warns.stop()
        self.patch_get_warn_setting.stop()
        self.patch_set_warn_limit.stop()
        self.patch_set_warn_strength.stop()
        self.patch_is_user_admin.stop()
        self.patch_user_can_warn.stop()
        self.patch_extract_user_and_text.stop()
        # self.patch_bot_can_kick.stop() # If it was patched

    # Test /warn command
    def test_warn_user_success(self):
        self.mock_is_user_admin.return_value = True
        self.mock_user_can_warn.return_value = True
        self.mock_extract_user_and_text.return_value = (self.target_user_mock.id, "Test reason")
        self.mock_warn_user.return_value = (1, ["Test reason"]) # num_warns, reasons_list
        self.mock_get_warn_setting.return_value = (3, False) # Limit 3, Hard mode

        warnings.warn_user_cmd(self.update, self.context)

        self.mock_warn_user.assert_called_once_with(self.target_user_mock.id, self.chat.id, "Test reason")
        self.update.effective_message.reply_text.assert_called_with(
            f"{self.target_user_mock.mention_html()} has 1/3 warnings.\nReason: Test reason", # Adjusted to match code's use of user_display_name
            parse_mode=telegram.ParseMode.HTML
        )
        self.context.bot.kick_chat_member.assert_not_called()

    def test_warn_user_reaches_limit_hard_mode_kick(self):
        self.mock_is_user_admin.return_value = True
        self.mock_user_can_warn.return_value = True
        self.mock_extract_user_and_text.return_value = (self.target_user_mock.id, "Final warning")
        self.mock_warn_user.return_value = (3, ["Reason1", "Reason2", "Final warning"])
        self.mock_get_warn_setting.return_value = (3, False) # Limit 3, Hard mode
        # chat.get_member(bot.id).can_restrict_members is already True by default in setUp

        warnings.warn_user_cmd(self.update, self.context)

        self.mock_warn_user.assert_called_once_with(self.target_user_mock.id, self.chat.id, "Final warning")
        self.update.effective_message.reply_text.assert_any_call( # Check for the kick message
            f"{self.target_user_mock.mention_html()} has been kicked due to reaching the warning limit (3/3).",
            parse_mode=telegram.ParseMode.HTML
        )
        self.context.bot.kick_chat_member.assert_called_once_with(self.chat.id, self.target_user_mock.id)

    def test_warn_user_reaches_limit_hard_mode_kick_no_perm(self):
        self.mock_is_user_admin.return_value = True
        self.mock_user_can_warn.return_value = True
        self.mock_extract_user_and_text.return_value = (self.target_user_mock.id, "Final warning")
        self.mock_warn_user.return_value = (3, ["Reason1", "Reason2", "Final warning"])
        self.mock_get_warn_setting.return_value = (3, False) # Limit 3, Hard mode

        # Simulate bot not having kick permission
        bot_member_no_kick_perm = MagicMock()
        bot_member_no_kick_perm.can_restrict_members = False
        self.chat.get_member.side_effect = lambda user_id: bot_member_no_kick_perm if user_id == self.bot.id else self.target_user_member_mock

        warnings.warn_user_cmd(self.update, self.context)

        self.mock_warn_user.assert_called_once_with(self.target_user_mock.id, self.chat.id, "Final warning")
        self.update.effective_message.reply_text.assert_any_call(
            f"{self.target_user_mock.mention_html()} has reached the warning limit (3/3) but I don't have permission to kick users here.",
            parse_mode=telegram.ParseMode.HTML
        )
        self.context.bot.kick_chat_member.assert_not_called()


    def test_warn_user_reaches_limit_soft_mode(self):
        self.mock_is_user_admin.return_value = True
        self.mock_user_can_warn.return_value = True
        self.mock_extract_user_and_text.return_value = (self.target_user_mock.id, "Final warning")
        self.mock_warn_user.return_value = (3, ["Reason1", "Reason2", "Final warning"])
        self.mock_get_warn_setting.return_value = (3, True) # Limit 3, Soft mode

        warnings.warn_user_cmd(self.update, self.context)

        self.mock_warn_user.assert_called_once_with(self.target_user_mock.id, self.chat.id, "Final warning")
        self.update.effective_message.reply_text.assert_any_call(
             f"{self.target_user_mock.mention_html()} has reached the warning limit (3/3) but soft mode is on, so no automated action will be taken.",
             parse_mode=telegram.ParseMode.HTML
        )
        self.context.bot.kick_chat_member.assert_not_called()

    def test_warn_user_no_permission(self):
        self.mock_is_user_admin.return_value = False # User is not admin
        self.mock_extract_user_and_text.return_value = (self.target_user_mock.id, "Test reason")
        # user_can_warn will also be False based on is_user_admin typically

        warnings.warn_user_cmd(self.update, self.context)
        self.update.effective_message.reply_text.assert_called_with("You don't have permission to warn this user.")
        self.mock_warn_user.assert_not_called()

    # Test /warnings command
    def test_get_warnings_success(self):
        self.mock_extract_user_and_text.return_value = (self.target_user_mock.id, None)
        self.mock_get_warns.return_value = (2, ["Reason 1", "Reason 2"]) # num_warns, reasons_list
        self.mock_get_warn_setting.return_value = (3, False) # warn_limit, soft_warn

        warnings.get_warnings_cmd(self.update, self.context)
        expected_reasons_str = "\n".join([f" - {html.escape(r)}" for r in ["Reason 1", "Reason 2"]])
        self.update.effective_message.reply_text.assert_called_with(
            f"{self.target_user_mock.mention_html()} has 2/3 warning(s) in this chat:\n{expected_reasons_str}",
            parse_mode=telegram.ParseMode.HTML
        )

    def test_get_warnings_no_warnings(self):
        self.mock_extract_user_and_text.return_value = (self.target_user_mock.id, None)
        self.mock_get_warns.return_value = (0, [])
        self.mock_get_warn_setting.return_value = (3, False)

        warnings.get_warnings_cmd(self.update, self.context)
        self.update.effective_message.reply_text.assert_called_with(
            f"{self.target_user_mock.mention_html()} has no warnings in this chat.",
            parse_mode=telegram.ParseMode.HTML
        )

    # Test /resetwarns command
    def test_reset_warnings_success(self):
        self.mock_is_user_admin.return_value = True
        self.mock_user_can_warn.return_value = True
        self.mock_extract_user_and_text.return_value = (self.target_user_mock.id, None)

        warnings.reset_warnings_cmd(self.update, self.context)

        self.mock_reset_warns.assert_called_once_with(self.target_user_mock.id, self.chat.id)
        self.update.effective_message.reply_text.assert_called_with(
            f"Warnings for {self.target_user_mock.mention_html()} have been reset.",
            parse_mode=telegram.ParseMode.HTML
        )

    # Test /setwarnlimit command
    def test_set_warn_limit_success(self):
        self.mock_is_user_admin.return_value = True
        self.context.args = ["5"]

        warnings.set_warn_limit_cmd(self.update, self.context)

        self.mock_set_warn_limit.assert_called_once_with(self.chat.id, 5)
        self.update.effective_message.reply_text.assert_called_with("Warning limit has been set to 5.")

    def test_set_warn_limit_invalid_arg(self):
        self.mock_is_user_admin.return_value = True
        self.context.args = ["abc"] # Invalid limit

        warnings.set_warn_limit_cmd(self.update, self.context)
        self.update.effective_message.reply_text.assert_called_with("Please provide a valid number for the warning limit (e.g., /setwarnlimit 3).")

    # Test /setwarnmode command
    def test_set_warn_mode_success_soft(self):
        self.mock_is_user_admin.return_value = True
        self.context.args = ["soft"]

        warnings.set_warn_mode_cmd(self.update, self.context)

        self.mock_set_warn_strength.assert_called_once_with(self.chat.id, True)
        self.update.effective_message.reply_text.assert_called_with("Warning mode has been set to <b>soft</b>.", parse_mode=telegram.ParseMode.HTML)

    def test_set_warn_mode_success_hard(self):
        self.mock_is_user_admin.return_value = True
        self.context.args = ["hard"]

        warnings.set_warn_mode_cmd(self.update, self.context)

        self.mock_set_warn_strength.assert_called_once_with(self.chat.id, False)
        self.update.effective_message.reply_text.assert_called_with("Warning mode has been set to <b>hard</b>.", parse_mode=telegram.ParseMode.HTML)

if __name__ == '__main__':
    unittest.main()
```
