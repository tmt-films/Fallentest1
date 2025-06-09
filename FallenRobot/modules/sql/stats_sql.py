import datetime
import threading

from sqlalchemy import Column, Integer, BigInteger, String, DateTime, func, distinct
from sqlalchemy.ext.declarative import declarative_base

# Assuming BASE and SESSION are correctly set up in FallenRobot.modules.sql
# If not, this structure needs to be adapted.
# For this subtask, we'll assume they can be imported or are standard.
from FallenRobot.modules.sql import BASE, SESSION
from FallenRobot import LOGGER # For logging errors

class ChatActivity(BASE):
    __tablename__ = "chat_activity"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(14), nullable=False) # Assuming chat_id is like '-1001234567890'
    user_id = Column(BigInteger, nullable=False)
    message_id = Column(BigInteger, nullable=False) # Message ID from Telegram
    timestamp = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    message_type = Column(String(20), nullable=False) # e.g., 'text', 'photo', 'sticker'

    def __init__(self, chat_id, user_id, message_id, message_type, timestamp=None):
        self.chat_id = str(chat_id)
        self.user_id = user_id
        self.message_id = message_id
        self.message_type = message_type
        if timestamp: # Allow providing timestamp, else default kicks in
            self.timestamp = timestamp
        else:
            self.timestamp = datetime.datetime.utcnow()


    def __repr__(self):
        return f"<ChatActivity from user {self.user_id} in chat {self.chat_id} at {self.timestamp}>"

# Create the table in the database if it doesn't exist
# This is often handled by BASE.metadata.create_all(engine) at startup
# but can be explicitly called for a new table.
# Ensure the bind is correctly obtained. If SESSION is a scoped_session,
# SESSION.get_bind() or SESSION.bind should work.
try:
    ChatActivity.__table__.create(bind=SESSION.get_bind(), checkfirst=True)
except Exception as e:
    LOGGER.error(f"Could not create chat_activity table: {e}") # Log if table creation fails

STATS_INSERTION_LOCK = threading.RLock()

def log_message(chat_id: str, user_id: int, message_id: int, message_type: str, timestamp: datetime.datetime):
    """
    Logs a message activity to the database.
    :param chat_id: ID of the chat
    :param user_id: ID of the user who sent the message
    :param message_id: ID of the message
    :param message_type: Type of message (e.g., 'text', 'photo')
    :param timestamp: Timestamp of the message (datetime object)
    """
    with STATS_INSERTION_LOCK:
        session = SESSION() # Create a new session for this operation
        try:
            activity_log = ChatActivity(
                chat_id=str(chat_id), # Ensure chat_id is string
                user_id=user_id,
                message_id=message_id,
                message_type=message_type,
                timestamp=timestamp
            )
            session.add(activity_log)
            session.commit()
        except Exception as e:
            LOGGER.exception(f"Error logging message to ChatActivity for chat_id {chat_id}, user_id {user_id}: {e}")
            session.rollback()
            # Not re-raising here to prevent a single failed log from crashing other things,
            # but the error is logged. Depending on desired behavior, could re-raise.
        finally:
            session.close()

# Query functions for chat statistics

def get_total_messages_in_chat(chat_id_str: str) -> int:
    """
    Gets the total number of logged messages in a specific chat.
    :param chat_id_str: The chat ID (as a string)
    :return: Total number of messages, or 0 if none.
    """
    session = SESSION()
    try:
        return session.query(func.count(ChatActivity.id)).filter(ChatActivity.chat_id == chat_id_str).scalar() or 0
    except Exception as e:
        LOGGER.exception(f"Error getting total messages for chat {chat_id_str}: {e}")
        return 0 # Return 0 on error
    finally:
        session.close()

def get_unique_users_count_in_chat(chat_id_str: str) -> int:
    """
    Gets the total number of unique users who have sent messages in a specific chat.
    :param chat_id_str: The chat ID (as a string)
    :return: Total number of unique users, or 0 if none.
    """
    session = SESSION()
    try:
        return session.query(func.count(distinct(ChatActivity.user_id))).filter(ChatActivity.chat_id == chat_id_str).scalar() or 0
    except Exception as e:
        LOGGER.exception(f"Error getting unique users count for chat {chat_id_str}: {e}")
        return 0
    finally:
        session.close()

def get_top_posters_in_chat(chat_id_str: str, limit: int = 5) -> list[tuple[int, int]]:
    """
    Gets the top posters in a specific chat.
    :param chat_id_str: The chat ID (as a string)
    :param limit: The maximum number of top posters to return
    :return: A list of tuples, where each tuple is (user_id, message_count). Empty list on error or no data.
    """
    session = SESSION()
    try:
        # Query for user_id and their message count, group by user_id, order by count, limit results
        return (
            session.query(ChatActivity.user_id, func.count(ChatActivity.id).label('msg_count'))
            .filter(ChatActivity.chat_id == chat_id_str)
            .group_by(ChatActivity.user_id)
            .order_by(func.count(ChatActivity.id).desc())
            .limit(limit)
            .all()
        )
    except Exception as e:
        LOGGER.exception(f"Error getting top posters for chat {chat_id_str}: {e}")
        return [] # Return empty list on error
    finally:
        session.close()
```
