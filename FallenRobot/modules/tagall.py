import html
import threading
import time # Required for potential delays if used, though not explicitly in this version.
from telegram import Update, ParseMode, TelegramError
from telegram.ext import CallbackContext, CommandHandler, Filters
from FallenRobot import dispatcher, LOGGER
from FallenRobot.modules.helper_funcs.chat_status import user_admin # Assuming this decorator handles admin checks
# We might need a specific check if the bot is admin for fetching members, e.g., context.bot.get_chat_member(chat.id, context.bot.id).is_administrator
# For now, we'll rely on the functions succeeding or failing if permissions are missing.

# In-memory store for active tagall tasks
# Structure: {chat_id: {'running': True}}
ACTIVE_TAGALL_TASKS = {}
TAGALL_LOCK = threading.RLock() # Using RLock if nested lock acquisition might occur, though not strictly necessary here.

@user_admin # Ensures only admins can use this
def tagall_command(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user # Admin user
    bot = context.bot
    args = context.args

    # Check if bot is admin
    try:
        bot_member = chat.get_member(bot.id)
        if not bot_member.is_administrator: # More direct check
             update.effective_message.reply_text("I need to be an admin with all permissions in this chat to perform this action.")
             return
    except TelegramError as e:
        LOGGER.warning(f"Failed to check bot admin status in chat {chat.id}: {e}")
        update.effective_message.reply_text("Could not verify my own admin status. Please ensure I have full admin rights.")
        return

    with TAGALL_LOCK:
        if chat.id in ACTIVE_TAGALL_TASKS and ACTIVE_TAGALL_TASKS[chat.id].get('running', False):
            update.effective_message.reply_text(
                "A /tagall operation is already in progress for this chat. "
                "Use /stoptagall to cancel it if needed."
            )
            return
        ACTIVE_TAGALL_TASKS[chat.id] = {'running': True, 'message_id': None}

    tag_message_text = " ".join(args) if args else "Hi everyone!"

    initial_reply = None
    try:
        initial_reply = update.effective_message.reply_text(
            f"Starting to tag all members... (Requested by: {user.mention_html()})\n"
            "This might take a while for large groups. Use /stoptagall to cancel.",
            parse_mode=ParseMode.HTML
        )
        with TAGALL_LOCK: # Store message_id for potential edit on cancel
            if chat.id in ACTIVE_TAGALL_TASKS:
                 ACTIVE_TAGALL_TASKS[chat.id]['message_id'] = initial_reply.message_id
    except TelegramError as e:
        LOGGER.error(f"Failed to send initial reply for /tagall in chat {chat.id}: {e}")
        with TAGALL_LOCK:
            if chat.id in ACTIVE_TAGALL_TASKS:
                del ACTIVE_TAGALL_TASKS[chat.id]
        return

    members_text_list = []
    member_count = 0
    actual_members_data = [] # To store (simulated) fetched members

    try:
        # --- Conceptual Real Member Fetching Block ---
        LOGGER.info(f"Starting member fetching for chat {chat.id} by {user.id}")
        # In a real implementation, this is where you'd use context.bot methods
        # For example:
        # for member in context.bot.get_chat_members(chat.id, limit=X): # Fictional method, actual API might differ
        #     with TAGALL_LOCK:
        #         if not ACTIVE_TAGALL_TASKS.get(chat.id, {}).get('running', False):
        #             LOGGER.info(f"Tagall cancelled during member fetching in chat {chat.id}")
        #             raise StopIteration # Or some other way to break out
        #     actual_members_data.append({'id': member.user.id, 'first_name': member.user.first_name, 'is_bot': member.user.is_bot})
        #     if len(actual_members_data) >= 500: # Safety break
        #         LOGGER.warning(f"Fetched 500 members for chat {chat.id}, stopping fetch early.")
        #         break
        #     time.sleep(0.01) # Small delay if iterating through many members

        # For this subtask: Simulate fetching a small list of users
        actual_members_data = [
            {'id': 12345, 'first_name': 'RealUser1', 'is_bot': False},
            {'id': 67890, 'first_name': 'RealUser2', 'is_bot': False},
            {'id': 10112, 'first_name': 'BotTest', 'is_bot': True},
            {'id': 13141, 'first_name': 'RealUser3', 'is_bot': False},
        ]
        LOGGER.info(f"Successfully fetched/simulated {len(actual_members_data)} members for chat {chat.id}")
        # --- End Conceptual Real Member Fetching Block ---

        # Check if cancelled during the (simulated) fetch process
        with TAGALL_LOCK:
            if not ACTIVE_TAGALL_TASKS.get(chat.id, {}).get('running', False):
                if initial_reply:
                    try: initial_reply.edit_text("Tagall operation cancelled by admin during member fetching.")
                    except TelegramError: pass
                LOGGER.info(f"/tagall for chat {chat.id} was cancelled during member fetching.")
                # Ensure cleanup is handled in finally block, so just return
                return

        for mem_user_data in actual_members_data: # Iterate over the new list
            # Cancellation check inside the loop is still important for real fetching if it's a long list
            with TAGALL_LOCK:
                if not ACTIVE_TAGALL_TASKS.get(chat.id, {}).get('running', False):
                    # No need to edit initial_reply here again, it's handled by the check before this loop
                    # or after the fetching block.
                    LOGGER.info(f"/tagall for chat {chat.id} was cancelled before processing all fetched members.")
                    return # Exit if cancelled

            if not mem_user_data['is_bot']:
                mention = f"<a href='tg://user?id={mem_user_data['id']}'>{html.escape(mem_user_data['first_name'])}</a>"
                members_text_list.append(mention)
                member_count += 1

        if not members_text_list:
            if initial_reply:
                try: initial_reply.edit_text("Could not find any non-bot members to tag from the fetched list.")
                except TelegramError: pass
        else:
            # Construct the message
            base_message_text = f"{html.escape(tag_message_text)}\n\n"
            current_message_part = base_message_text

            for idx, mention in enumerate(members_text_list):
                with TAGALL_LOCK:
                    if not ACTIVE_TAGALL_TASKS.get(chat.id, {}).get('running', False):
                        if initial_reply:
                            try:
                                initial_reply.edit_text("Tagall operation cancelled by admin during message construction.")
                            except TelegramError: pass
                        LOGGER.info(f"/tagall for chat {chat.id} was cancelled before sending.")
                        return

                if len(current_message_part.encode('utf-8')) + len(mention.encode('utf-8')) + 1 > 4096: # Check byte length
                    try:
                        context.bot.send_message(chat.id, current_message_part, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                        time.sleep(0.5) # Small delay to avoid hitting rate limits
                    except TelegramError as e:
                        LOGGER.error(f"Failed to send a part of /tagall message in chat {chat.id}: {e}")
                        if initial_reply:
                            try:
                                initial_reply.edit_text(f"Error sending mentions: {e}. Process halted.")
                            except TelegramError: pass
                        return
                    current_message_part = base_message_text

                current_message_part += mention + " "

            # Send the last part
            if current_message_part.strip() != base_message_text.strip() and current_message_part.strip() :
                try:
                    context.bot.send_message(chat.id, current_message_part.strip(), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                except TelegramError as e:
                    LOGGER.error(f"Failed to send the last part of /tagall message in chat {chat.id}: {e}")
                    if initial_reply:
                        try:
                            initial_reply.edit_text(f"Error sending final batch of mentions: {e}. Some users may not have been tagged.")
                        except TelegramError: pass

            if initial_reply:
                try:
                    initial_reply.delete()
                except TelegramError: pass # If message already deleted or too old

            try:
                context.bot.send_message(chat.id, f"Finished tagging {member_count} members. (Requested by: {user.mention_html()})", parse_mode=ParseMode.HTML)
            except TelegramError as e:
                 LOGGER.warning(f"Failed to send /tagall confirmation message in {chat.id}: {e}")

    except Exception as e:
        LOGGER.error(f"Error in /tagall for chat {chat.id}: {e}", exc_info=True)
        if initial_reply:
            try:
                initial_reply.edit_text(f"An error occurred: {html.escape(str(e))}. Please check logs.")
            except TelegramError:
                pass
        # Ensure cleanup even if an error occurs during the main processing block
        # The finally block will handle this.

    except StopIteration: # Custom exception to break from simulated fetch on cancel
        LOGGER.info(f"Member fetching explicitly stopped for chat {chat.id}.")
        if initial_reply:
            try: initial_reply.edit_text("Tagall operation cancelled during member fetching.")
            except TelegramError: pass
        # Fall through to finally for cleanup

    except TelegramError as te: # Catch Telegram specific errors during conceptual fetch
        LOGGER.error(f"TelegramError during member fetching for chat {chat.id}: {te}")
        if initial_reply:
            try: initial_reply.edit_text(f"Error fetching members: {html.escape(str(te))}. Process halted.")
            except TelegramError: pass
        # Fall through to finally for cleanup

    finally:
        with TAGALL_LOCK:
            if chat.id in ACTIVE_TAGALL_TASKS:
                del ACTIVE_TAGALL_TASKS[chat.id]
                LOGGER.info(f"Cleaned up ACTIVE_TAGALL_TASKS for chat {chat.id}")

@user_admin
def stoptagall_command(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    # message_id_to_edit = None # Not strictly needed here, initial_reply edit is handled in tagall_command
    with TAGALL_LOCK:
        task = ACTIVE_TAGALL_TASKS.get(chat_id)
        if task and task.get('running', False):
            task['running'] = False # Set the flag to false
            # initial_message_id = task.get('message_id') # Get the message_id if we want to edit it from here
            # if initial_message_id:
            #     try:
            #         context.bot.edit_message_text("Tagall operation cancellation requested...", chat_id=chat_id, message_id=initial_message_id)
            #     except TelegramError as e:
            #         LOGGER.warning(f"Failed to edit message on stoptagall: {e}")
            update.effective_message.reply_text("Requested to stop the current /tagall operation. It will halt shortly.")
        else:
            update.effective_message.reply_text("No /tagall operation is currently active in this chat.")

TAGALL_HANDLER = CommandHandler("tagall", tagall_command, filters=Filters.chat_type.groups, run_async=True)
STOPTAGALL_HANDLER = CommandHandler("stoptagall", stoptagall_command, filters=Filters.chat_type.groups, run_async=True)

dispatcher.add_handler(TAGALL_HANDLER)
dispatcher.add_handler(STOPTAGALL_HANDLER)

__mod_name__ = "Tag All"
__help__ = """
Admins can use this module to mention all members in the chat.

*Admin Commands:*
  ❍ /tagall [message]: Mentions all non-bot members in the chat along with the provided message.
    If no message is given, defaults to "Hi everyone!".
    *Note:* For very large groups, this might be slow, send multiple messages, or hit Telegram limits. The process can be cancelled.
  ❍ /stoptagall: Requests to stop an ongoing /tagall operation.
"""

__handlers__ = [TAGALL_HANDLER, STOPTAGALL_HANDLER]

# TODO: Replace simulated_members_data with actual logic to fetch chat members.
# This might involve:
# 1. Using `context.bot.get_chat_members_count(chat.id)` and then iterating with a library helper if available.
# 2. Or, if the library doesn't provide an iterator for all members, this feature might be limited
#    to smaller groups or require different strategies (e.g. fetching admins + recent members).
# 3. Permissions: Ensure the bot has rights to get member lists. `chat.get_member(bot.id)` and checking `is_administrator`
#    is a basic check, but specific permissions like `can_manage_chat` or similar might be implicitly needed by some
#    library functions that would fetch all members.
# 4. Rate limiting: Add small delays (e.g. `time.sleep(0.1)`) inside the member loop or message sending loop if
#    Telegram's rate limits are hit, though `python-telegram-bot` usually handles these gracefully.
#    A `time.sleep(0.5)` was added after sending a message part.
```
