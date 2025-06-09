from telegram import Update, Filters
from telegram.ext import CallbackContext, MessageHandler

# Assuming FallenRobot is in the Python path
from FallenRobot import dispatcher, LOGGER
from FallenRobot.modules.sql import stats_sql

# Define a function to determine message type
def get_message_type(message: Update.message) -> str: # Added type hint for clarity
    if message.text:
        return "text"
    elif message.photo:
        return "photo"
    elif message.sticker:
        return "sticker"
    elif message.video:
        return "video"
    elif message.audio:
        return "audio"
    elif message.voice:
        return "voice"
    elif message.document:
        return "document"
    elif message.contact:
        return "contact"
    elif message.location:
        return "location"
    elif message.venue:
        return "venue"
    elif message.poll:
        return "poll"
    elif message.new_chat_members:
        return "new_chat_members"
    elif message.left_chat_member:
        return "left_chat_member"
    # Add more types as needed, e.g., game, video_note, invoice, successful_payment
    elif message.game:
        return "game"
    elif message.video_note:
        return "video_note"
    elif message.invoice:
        return "invoice"
    elif message.successful_payment:
        return "successful_payment"
    return "unknown"

def log_incoming_message(update: Update, context: CallbackContext):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user or not message: # Basic checks
        # Could add a log here if we expect these to always be present for handled messages
        return

    # Avoid logging messages from bots if desired (can be configurable later)
    if user.is_bot: # Explicitly skip bots, including self if bot has sent a message to a group
        return

    # Avoid logging messages from certain user IDs like anonymous admins or specific bot IDs if needed
    # Telegram's group anonymous user ID is 1087968824, channel anonymous is 136817688 (@Channel_Bot)
    # Service messages from ID 777000 (Telegram) e.g. for pinned messages are not handled by MessageHandler usually
    if user.id in [1087968824, 136817688]:
        return

    try:
        chat_id = str(chat.id)
        user_id = user.id
        message_id = message.message_id
        timestamp = message.date # This is a datetime object

        # Determine message type
        msg_type = get_message_type(message)

        # Don't log "unknown" if it's just a message with no specific media type but has text (already "text")
        # The current get_message_type handles this: if message.text, it returns "text" first.
        # If msg_type is "unknown" it implies none of the other specific types matched.
        if msg_type == "unknown" and not message.text and not message.caption: # only log unknown if truly no content
            # This might happen for service messages not caught by specific types, or future telegram types
            # For now, we can choose to log them or not. Let's log them to see what they are.
            pass


        stats_sql.log_message(
            chat_id=chat_id,
            user_id=user_id,
            message_id=message_id,
            message_type=msg_type,
            timestamp=timestamp
        )
    except Exception as e:
        # Log detailed error if something goes wrong during extraction or DB logging
        # Avoid crashing the bot due to a logging failure
        LOGGER.error(f"Failed to log message for stats in chat {chat.id if chat else 'UnknownChat'}: {e}", exc_info=True)


# Define a handler group number.
STATS_LOGGER_HANDLER_GROUP = 15

# Create the handler
# Filters.update.edited_message is for edited_message, not ~Filters.update.edited_message
# We want to log new messages, not edits. So, if an update is an edit, it will have `update.edited_message`
# and `update.message` will be None. `Filters.message` implicitly handles this.
# `Filters.all` might be too broad if we only care about user messages with content.
# `Filters.update` does not exist. It's `Filters.update.edited_message` or similar.
# A more precise filter for typical user messages:
log_message_filters = (
    (Filters.text | Filters.sticker | Filters.photo | Filters.video | Filters.document |
     Filters.audio | Filters.voice | Filters.contact | Filters.location | Filters.venue | Filters.poll |
     Filters.video_note | Filters.game | Filters.new_chat_members | Filters.left_chat_member) &
    Filters.chat_type.groups &
    (~Filters.status_update) # Exclude service messages like "User X joined" if not covered by new_chat_members etc.
    # Note: Filters.update.edited_message is not what we want to filter out with ~.
    # We just want new messages. MessageHandler by default handles `update.message`.
    # If `update.edited_message` is present, `update.message` is None.
    # So, MessageHandler on Filters.text (etc.) won't fire for edits.
)


STATS_HANDLER = MessageHandler(
    log_message_filters,
    log_incoming_message,
    run_async=True
)

# Add to dispatcher
dispatcher.add_handler(STATS_HANDLER, STATS_LOGGER_HANDLER_GROUP)

# No __mod_name__, __help__, or __handlers__ needed if this is a background logging module.
```
