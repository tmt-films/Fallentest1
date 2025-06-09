import shlex
from telegram import Update, ParseMode, TelegramError, Filters
from telegram.ext import CommandHandler, CallbackContext
from FallenRobot import dispatcher

# If CMD_HANDLER_GROUP is standard, it would be imported from FallenRobot or a constants module
# For now, let's assume a default group or define one if necessary.
# from FallenRobot import CMD_HANDLER_GROUP # Example if it exists
CMD_HANDLER_GROUP = 10 # Placeholder if not globally defined

def poll_command(update: Update, context: CallbackContext):
    message = update.effective_message
    chat = update.effective_chat

    try:
        args_text = message.text.split(None, 1)[1]
    except IndexError:
        message.reply_text(
            "<b>Please provide a question and options for the poll.</b>\n\n"
            "<b>Usage:</b> <code>/poll \"Your Question\" \"Option 1\" \"Option 2\" \"Option 3\" ...</code>\n"
            "You need at least one question and two options.\n"
            "Options must be between 1 and 100 characters. Question between 1 and 300.",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        # Using shlex to split allows for options with spaces if they are quoted
        parsed_args = shlex.split(args_text)
    except ValueError as e:
        message.reply_text(f"Error parsing arguments: {e}. Ensure quotes are properly matched.")
        return

    if not parsed_args:
        message.reply_text("No question or options provided after the command.")
        return

    question = parsed_args[0]
    options = parsed_args[1:]

    # Validation
    if not question:
        message.reply_text("Poll question cannot be empty.")
        return

    if len(question) > 300: # Telegram API limit for question length (was 255, now 300)
        message.reply_text("Poll question is too long. Maximum 300 characters.")
        return

    if not options or len(options) < 2:
        message.reply_text("You need to provide at least two options for the poll.")
        return

    if len(options) > 10:
        message.reply_text("You can provide a maximum of 10 options for the poll.")
        return

    for opt in options:
        if not opt:
            message.reply_text("Poll options cannot be empty.")
            return
        if len(opt) > 100:
            message.reply_text(
                f"Option '{opt[:50]}...' is too long. Maximum 100 characters per option."
            )
            return

    try:
        context.bot.send_poll(
            chat_id=chat.id,
            question=question,
            options=options,
            is_anonymous=True,  # Defaulting to anonymous polls
        )
    except TelegramError as e:
        message.reply_text(f"An error occurred while sending the poll: {e.message}")
    except Exception as e:
        message.reply_text(f"An unexpected error occurred: {e}")


POLL_HANDLER = CommandHandler("poll", poll_command, filters=Filters.chat_type.groups, run_async=True)

dispatcher.add_handler(POLL_HANDLER, group=CMD_HANDLER_GROUP) # Assuming CMD_HANDLER_GROUP

__mod_name__ = "Polls"
__help__ = """
Create polls in your chat.

**Command:** `/poll`

**Usage:**
`/poll "Your Question" "Option 1" "Option 2" ["Option 3" ... "Option 10"]`

- The question and each option should be enclosed in double quotes if they contain spaces.
- You must provide a question and at least two options.
- A maximum of 10 options are allowed.
- Question length: 1-300 characters.
- Option length: 1-100 characters.

**Example:**
`/poll "What's your favorite color?" "Red" "Blue" "Green"`
"""

__handlers__ = [(POLL_HANDLER, CMD_HANDLER_GROUP)]
