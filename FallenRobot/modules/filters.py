import html
from telegram import Update, ParseMode, Filters, Message
from telegram.ext import CommandHandler, MessageHandler, CallbackContext
from telegram.error import BadRequest

from FallenRobot.modules.sql import filters_sql as sql
from FallenRobot.modules.helper_funcs.chat_status import (
    is_user_admin,
    bot_can_delete_messages,
    user_admin_no_reply, # Using this for admin check, replies if not admin
    # bot_admin_no_reply # Not used directly here, but good to be aware of
)
from FallenRobot.modules.log_channel import loggable
from FallenRobot import dispatcher, DRAGONS, DEV_USERS, OWNER_ID, SUDO_USERS, WHITELIST_USERS # For admin/bot exemption if used directly in handler

FILTER_HANDLER_GROUP = 6 # Lower group number for earlier processing
CMD_HANDLER_GROUP = 15 # Arbitrary group for command handlers

@user_admin_no_reply
@loggable
def add_filter_cmd(update: Update, context: CallbackContext) -> str:
    args = context.args
    chat = update.effective_chat
    user = update.effective_user

    if not args:
        update.effective_message.reply_text("Please specify a keyword to filter!")
        return ""

    keyword = " ".join(args).lower()

    if len(keyword) > 100: # Arbitrary limit for keyword length
        update.effective_message.reply_text("Filter keyword is too long. Keep it under 100 characters.")
        return ""

    sql.add_filter(chat.id, keyword)
    update.effective_message.reply_text(f"Added filter for '<code>{html.escape(keyword)}</code>'.", parse_mode=ParseMode.HTML)
    return f"<b>{html.escape(chat.title)}:</b>\n#ADDFILTER\n<b>Admin:</b> {user.mention_html()}\n<b>Keyword:</b> {html.escape(keyword)}"

@user_admin_no_reply
@loggable
def rm_filter_cmd(update: Update, context: CallbackContext) -> str:
    args = context.args
    chat = update.effective_chat
    user = update.effective_user

    if not args:
        update.effective_message.reply_text("Please specify a keyword to remove!")
        return ""

    keyword = " ".join(args).lower()

    if sql.remove_filter(chat.id, keyword):
        update.effective_message.reply_text(f"Removed filter for '<code>{html.escape(keyword)}</code>'.", parse_mode=ParseMode.HTML)
        return f"<b>{html.escape(chat.title)}:</b>\n#RMFILTER\n<b>Admin:</b> {user.mention_html()}\n<b>Keyword:</b> {html.escape(keyword)}"
    else:
        update.effective_message.reply_text("This filter doesn't exist or was already removed.")
        return "" # No need to log if filter didn't exist

def list_filters_cmd(update: Update, context: CallbackContext):
    chat = update.effective_chat
    all_filters_tuples = sql.get_chat_filters(chat.id)

    if not all_filters_tuples:
        update.effective_message.reply_text("No filters are active in this chat.")
        return

    filter_list = "<b>Active filters in this chat:</b>\n"
    for keyword_tuple in all_filters_tuples:
        filter_list += f"- <code>{html.escape(keyword_tuple[0])}</code>\n"

    # Consider using a Message Paginator if the list can be very long
    update.effective_message.reply_text(filter_list, parse_mode=ParseMode.HTML)


def filter_message_handler(update: Update, context: CallbackContext):
    chat = update.effective_chat
    message = update.effective_message # type: Message
    user = update.effective_user # User who sent the message

    # Exemptions for admins and bot could be done here
    # For example:
    # if user and user.id in (DRAGONS + DEV_USERS + SUDO_USERS + WHITELIST_USERS + [OWNER_ID, context.bot.id]):
    #     return
    # Or more granularly with is_user_admin(chat, user.id) if only chat admins are exempt
    if user and is_user_admin(chat, user.id): # Simple exemption for chat admins
         return

    if not chat or not message.text:
        return

    keywords_tuples = sql.get_chat_filters(chat.id)
    if not keywords_tuples:
        return

    message_text_lower = message.text.lower()

    for keyword_tuple in keywords_tuples:
        keyword = keyword_tuple[0]
        if keyword in message_text_lower: # Basic substring check
            if bot_can_delete_messages(chat, context.bot.id):
                try:
                    message.delete()
                except BadRequest as exc:
                    if exc.message == "Message to delete not found" or exc.message == "Message can't be deleted":
                        pass # Already deleted or can't be deleted by bot
                    else:
                        # Log other BadRequest errors if necessary
                        # log.warning(f"Error deleting message in filter: {exc}")
                        pass
            break # Stop after first match and action

# Handlers
ADD_FILTER_HANDLER = CommandHandler(["addfilter", "addf"], add_filter_cmd, filters=Filters.chat_type.groups, run_async=True)
RM_FILTER_HANDLER = CommandHandler(["rmfilter", "rmf"], rm_filter_cmd, filters=Filters.chat_type.groups, run_async=True)
LIST_FILTERS_HANDLER = CommandHandler(["filter", "filters", "listfilters", "listf"], list_filters_cmd, filters=Filters.chat_type.groups, run_async=True)
FILTER_MESSAGE_HANDLER = MessageHandler(
    Filters.text & Filters.chat_type.groups & (~Filters.update.edited_message) & (~Filters.via_bot) & (~Filters.forwarded),
    filter_message_handler,
    run_async=True
)


dispatcher.add_handler(ADD_FILTER_HANDLER, CMD_HANDLER_GROUP)
dispatcher.add_handler(RM_FILTER_HANDLER, CMD_HANDLER_GROUP)
dispatcher.add_handler(LIST_FILTERS_HANDLER, CMD_HANDLER_GROUP)
dispatcher.add_handler(FILTER_MESSAGE_HANDLER, FILTER_HANDLER_GROUP)


__mod_name__ = "Filters"
__help__ = """
Word filtering allows you to automatically delete messages containing specific keywords.

**Admin Commands:**
- /addfilter or /addf <keyword>: Adds a keyword to the filter list. Messages containing this keyword will be deleted. (Keywords are case-insensitive)
- /rmfilter or /rmf <keyword>: Removes a keyword from the filter list.
- /filters or /listfilters or /listf: Lists all active filters in the chat.

**Note:**
- Filters match anywhere in a message.
- If multiple filters match, the message is deleted on the first match.
- Chat admins are exempt from filters in their messages.
"""

__handlers__ = [
    (ADD_FILTER_HANDLER, CMD_HANDLER_GROUP),
    (RM_FILTER_HANDLER, CMD_HANDLER_GROUP),
    (LIST_FILTERS_HANDLER, CMD_HANDLER_GROUP),
    (FILTER_MESSAGE_HANDLER, FILTER_HANDLER_GROUP),
]
