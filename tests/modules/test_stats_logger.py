import unittest
from unittest.mock import MagicMock, patch, call # call is not used in provided tests but good for more complex arg checks
import datetime
import telegram # For Update, Chat, User, Message etc.

# Assuming FallenRobot is in the Python path
from FallenRobot.modules import stats_logger
# For accessing stats_sql.log_message and LOGGER if needed for patching
from FallenRobot.modules.sql import stats_sql
from FallenRobot import LOGGER as FALLEN_LOGGER # Assuming this is the project's LOGGER

class TestStatsLogger(unittest.TestCase):

    def setUp(self):
        self.update = MagicMock(spec=telegram.Update)
        self.context = MagicMock(spec=stats_logger.CallbackContext) # stats_logger.CallbackContext is fine
        self.message = MagicMock(spec=telegram.Message)
        self.chat = MagicMock(spec=telegram.Chat)
        self.user = MagicMock(spec=telegram.User)

        self.update.effective_message = self.message
        self.update.effective_chat = self.chat
        self.update.effective_user = self.user

        # chat.id in PTB is an int. stats_sql.log_message converts it to str.
        self.chat.id = -1001234567890
        self.user.id = 67890
        self.user.is_bot = False # Default to not a bot
        self.message.message_id = 101
        # Ensure message.date is timezone-aware if stats_sql expects it or db stores with timezone
        self.message.date = datetime.datetime.now(datetime.timezone.utc)

        # Reset message type attributes for each test
        self.reset_message_type_attrs()

    def reset_message_type_attrs(self):
        self.message.text = None
        self.message.photo = None
        self.message.sticker = None
        self.message.video = None
        self.message.audio = None
        self.message.voice = None
        self.message.document = None
        self.message.contact = None
        self.message.location = None
        self.message.venue = None
        self.message.poll = None
        self.message.new_chat_members = None
        self.message.left_chat_member = None
        self.message.game = None
        self.message.video_note = None
        self.message.invoice = None
        self.message.successful_payment = None
        self.message.caption = None # For media with captions

    # Test get_message_type function
    def test_get_message_type(self):
        # Order matters if a message can have multiple attributes (e.g. photo with caption -> text)
        # The current get_message_type prioritizes .text
        test_cases = {
            "text": "text", "photo": "photo", "sticker": "sticker", "video": "video",
            "audio": "audio", "voice": "voice", "document": "document",
            "contact": "contact", "location": "location", "venue": "venue",
            "poll": "poll",
            "new_chat_members": "new_chat_members", # Typically an array of User objects
            "left_chat_member": "left_chat_member", # Typically a User object
            "game": "game", "video_note": "video_note",
            "invoice": "invoice", "successful_payment": "successful_payment"
        }
        for attr, expected_type in test_cases.items():
            self.reset_message_type_attrs()
            # For attributes that are not just booleans (like new_chat_members list or left_chat_member object)
            if attr in ["new_chat_members", "left_chat_member"]:
                setattr(self.message, attr, [MagicMock(spec=telegram.User)] if attr == "new_chat_members" else MagicMock(spec=telegram.User))
            else:
                setattr(self.message, attr, MagicMock()) # Presence of attribute's mock is enough

            self.assertEqual(stats_logger.get_message_type(self.message), expected_type, f"Failed for type: {attr}")

        # Test unknown type
        self.reset_message_type_attrs()
        self.assertEqual(stats_logger.get_message_type(self.message), "unknown")

        # Test text with photo (text should take precedence in current get_message_type)
        self.reset_message_type_attrs()
        self.message.text = "Hello"
        self.message.photo = [MagicMock()] # Photo is a list of PhotoSize
        self.assertEqual(stats_logger.get_message_type(self.message), "text")


    @patch('FallenRobot.modules.sql.stats_sql.log_message')
    @patch('FallenRobot.modules.stats_logger.LOGGER')
    def test_log_incoming_message_text(self, mock_logger, mock_sql_log_message):
        self.reset_message_type_attrs()
        self.message.text = "Hello world"

        stats_logger.log_incoming_message(self.update, self.context)

        mock_sql_log_message.assert_called_once_with(
            chat_id=str(self.chat.id), # Ensure string conversion is tested
            user_id=self.user.id,
            message_id=self.message.message_id,
            message_type="text",
            timestamp=self.message.date
        )

    @patch('FallenRobot.modules.sql.stats_sql.log_message')
    @patch('FallenRobot.modules.stats_logger.LOGGER')
    def test_log_incoming_message_sticker(self, mock_logger, mock_sql_log_message):
        self.reset_message_type_attrs()
        self.message.sticker = MagicMock()

        stats_logger.log_incoming_message(self.update, self.context)

        mock_sql_log_message.assert_called_once_with(
            chat_id=str(self.chat.id),
            user_id=self.user.id,
            message_id=self.message.message_id,
            message_type="sticker",
            timestamp=self.message.date
        )

    @patch('FallenRobot.modules.sql.stats_sql.log_message')
    @patch('FallenRobot.modules.stats_logger.LOGGER')
    def test_log_incoming_message_user_is_bot(self, mock_logger, mock_sql_log_message):
        self.reset_message_type_attrs()
        self.user.is_bot = True
        self.message.text = "I am a bot"

        stats_logger.log_incoming_message(self.update, self.context)

        mock_sql_log_message.assert_not_called()

    @patch('FallenRobot.modules.sql.stats_sql.log_message')
    @patch('FallenRobot.modules.stats_logger.LOGGER')
    def test_log_incoming_message_user_is_group_anonymous(self, mock_logger, mock_sql_log_message):
        self.reset_message_type_attrs()
        self.user.id = 1087968824 # Group anonymous user
        self.message.text = "Anonymous message from group"

        stats_logger.log_incoming_message(self.update, self.context)

        mock_sql_log_message.assert_not_called()

    @patch('FallenRobot.modules.sql.stats_sql.log_message')
    @patch('FallenRobot.modules.stats_logger.LOGGER')
    def test_log_incoming_message_user_is_channel_anonymous(self, mock_logger, mock_sql_log_message):
        self.reset_message_type_attrs()
        self.user.id = 136817688 # Channel anonymous user (@Channel_Bot)
        self.message.text = "Anonymous message from channel" # Unlikely scenario for groups, but tests ID

        stats_logger.log_incoming_message(self.update, self.context)

        mock_sql_log_message.assert_not_called()


    @patch('FallenRobot.modules.sql.stats_sql.log_message', side_effect=Exception("DB Error"))
    @patch('FallenRobot.modules.stats_logger.LOGGER')
    def test_log_incoming_message_db_error(self, mock_logger, mock_sql_log_message_with_error):
        self.reset_message_type_attrs()
        self.message.text = "A message"

        stats_logger.log_incoming_message(self.update, self.context)

        mock_sql_log_message_with_error.assert_called_once()
        mock_logger.error.assert_called_once()
        self.assertIn(f"Failed to log message for stats in chat {str(self.chat.id)}", mock_logger.error.call_args[0][0])
        self.assertIn("DB Error", str(mock_logger.error.call_args[1]['exc_info'])) # Check if DB Error in exception info


if __name__ == '__main__':
    unittest.main()
```
