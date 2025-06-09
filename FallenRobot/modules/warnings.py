import html
import telegram # For telegram.error.BadRequest
from telegram import Update, ParseMode
from telegram.ext import CommandHandler, CallbackContext, Filters # Added Filters
from FallenRobot.modules.sql import warns_sql as sql
from FallenRobot.modules.helper_funcs.chat_status import (
    is_user_admin,
    user_can_warn,
    bot_can_delete_messages,
    # Consider bot_can_restrict_members if available and more specific
)
from FallenRobot.modules.helper_funcs.extraction import extract_user_and_text
from FallenRobot.modules.helper_funcs.string_handling import extract_time # Not strictly used in this diff but present
from FallenRobot.modules.log_channel import loggable
from FallenRobot import dispatcher # Main dispatcher for the bot

WARN_HANDLER_GROUP = 10
# DEL_WARN_HANDLER_GROUP will be used for resetwarns
# GET_WARN_HANDLER_GROUP will be used for warnings
# New handlers will use WARN_HANDLER_GROUP for simplicity or define new ones if needed
SETTINGS_HANDLER_GROUP = 11 # Example for new handlers

@loggable
def warn_user_cmd(update: Update, context: CallbackContext) -> str:
    args = context.args
    message = update.effective_message
    chat = update.effective_chat
    warner = update.effective_user

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("No user specified to warn.")
        return ""

    if user_id == context.bot.id:
        message.reply_text("I'm not going to warn myself, that's silly.")
        return ""

    if user_id in [777000, 1087968824]: # Anonymous / Group anons
        message.reply_text("Warning anonymous admins isn't supported.")
        return ""

    if not reason:
        reason = "No reason provided."

    if not is_user_admin(chat, warner.id) or not user_can_warn(chat, warner.id, user_id):
        message.reply_text("You don't have permission to warn this user.")
        return ""

    try:
        num_warns, _ = sql.warn_user(user_id, chat.id, reason) # reasons var not used here
    except Exception as e:
        message.reply_text(f"Error warning user: {e}")
        return f"ERROR: {e}"

    warn_limit, soft_warn = sql.get_warn_setting(chat.id)
    # User mention for logs - trying to get a display name
    try:
        user_member = chat.get_member(user_id)
        user_mention = user_member.user.mention_html()
        user_display_name = f"{user_mention} (<code>{user_id}</code>)"
    except telegram.error.BadRequest: # User not in chat or other issue
        user_display_name = f"User ID <code>{user_id}</code>"


    log_message = (
        f"<b>{html.escape(chat.title)}:</b>\n"
        f"#WARN\n"
        f"<b>Admin:</b> {warner.mention_html()}\n"
        f"<b>User:</b> {user_display_name}\n"
        f"<b>Reason:</b> {html.escape(reason)}\n"
        f"<b>Total Warns:</b> {num_warns}/{warn_limit}"
    )

    if num_warns >= warn_limit:
        if soft_warn:
            message.reply_text(
                f"{user_display_name} has reached the warning limit ({num_warns}/{warn_limit}) but soft mode is on, so no automated action will be taken.",
                parse_mode=ParseMode.HTML,
            )
            log_message += f"\n<b>Action:</b> Soft warn limit reached."
        else:
            # Check bot's permission to kick
            # bot_can_delete_messages is a proxy for admin rights, can_restrict_members is specific
            bot_member = chat.get_member(context.bot.id)
            if bot_member.can_restrict_members:
                try:
                    context.bot.kick_chat_member(chat.id, user_id)
                    message.reply_text(
                        f"{user_display_name} has been kicked due to reaching the warning limit ({num_warns}/{warn_limit}).",
                        parse_mode=ParseMode.HTML,
                    )
                    log_message += f"\n<b>Action:</b> User kicked."
                    # sql.reset_warns(user_id, chat.id) # Optionally reset warns after kick
                except telegram.error.BadRequest as exc:
                    if exc.message == "User_not_participant":
                        message.reply_text(f"{user_display_name} is not a participant, can't kick.", parse_mode=ParseMode.HTML)
                        log_message += f"\n<b>Action:</b> User not participant, couldn't kick."
                    elif "user is an administrator of the chat" in exc.message.lower():
                        message.reply_text(f"I can't kick an administrator: {user_display_name}.", parse_mode=ParseMode.HTML)
                        log_message += f"\n<b>Action:</b> User is admin, couldn't kick."
                    else:
                        message.reply_text(f"Could not kick {user_display_name}: {exc.message}", parse_mode=ParseMode.HTML)
                        log_message += f"\n<b>Action:</b> Failed to kick user - {exc.message}."
            else:
                message.reply_text(
                    f"{user_display_name} has reached the warning limit ({num_warns}/{warn_limit}) but I don't have permission to kick users here.",
                    parse_mode=ParseMode.HTML,
                )
                log_message += f"\n<b>Action:</b> Warn limit reached, but no permission to kick."
    else:
        message.reply_text(
            f"{user_display_name} has {num_warns}/{warn_limit} warnings.\nReason: {html.escape(reason)}",
            parse_mode=ParseMode.HTML,
        )

    return log_message


@loggable
def get_warnings_cmd(update: Update, context: CallbackContext) -> str:
    args = context.args
    message = update.effective_message
    chat = update.effective_chat

    user_id, _ = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("No user specified to check warnings for.")
        return ""

    try:
        user_member = chat.get_member(user_id)
        user_display_name = f"{user_member.user.mention_html()} (<code>{user_id}</code>)"
    except telegram.error.BadRequest: # User not in chat or other issue
        user_display_name = f"User ID <code>{user_id}</code>"


    num_warns, reasons = sql.get_warns(user_id, chat.id)

    if not num_warns or num_warns == 0:
        message.reply_text(f"{user_display_name} has no warnings in this chat.", parse_mode=ParseMode.HTML)
    else:
        reasons_str = "\n".join([f" - {html.escape(r)}" for r in reasons])
        warn_limit, _ = sql.get_warn_setting(chat.id)
        message.reply_text(
            f"{user_display_name} has {num_warns}/{warn_limit} warning(s) in this chat:\n{reasons_str}",
            parse_mode=ParseMode.HTML,
        )
    return "" # No log message needed for just getting warnings

@loggable
def reset_warnings_cmd(update: Update, context: CallbackContext) -> str:
    args = context.args
    message = update.effective_message
    chat = update.effective_chat
    admin = update.effective_user # Renamed from warner for clarity

    user_id, _ = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("No user specified to reset warnings for.")
        return ""

    try:
        user_member = chat.get_member(user_id)
        user_display_name = f"{user_member.user.mention_html()} (<code>{user_id}</code>)"
    except telegram.error.BadRequest: # User not in chat or other issue
        user_display_name = f"User ID <code>{user_id}</code>"


    if not is_user_admin(chat, admin.id) or not user_can_warn(chat, admin.id, user_id): # user_can_warn checks if admin can warn target
        message.reply_text("You don't have permission to reset warnings for this user.")
        return ""

    try:
        sql.reset_warns(user_id, chat.id)
        message.reply_text(f"Warnings for {user_display_name} have been reset.", parse_mode=ParseMode.HTML)
        return (
            f"<b>{html.escape(chat.title)}:</b>\n"
            f"#RESETWARNS\n"
            f"<b>Admin:</b> {admin.mention_html()}\n"
            f"<b>User:</b> {user_display_name}"
        )
    except Exception as e:
        message.reply_text(f"Error resetting warnings: {e}")
        return f"ERROR: {e}"

@loggable
def set_warn_limit_cmd(update: Update, context: CallbackContext) -> str:
    args = context.args
    message = update.effective_message
    chat = update.effective_chat
    admin = update.effective_user

    if not is_user_admin(chat, admin.id):
        message.reply_text("You need to be an admin to set the warning limit.")
        return ""

    if not args or not args[0].isdigit():
        message.reply_text("Please provide a valid number for the warning limit (e.g., /setwarnlimit 3).")
        return ""

    limit = int(args[0])
    if limit < 1:
        message.reply_text("Warning limit must be at least 1.")
        return ""

    try:
        sql.set_warn_limit(chat.id, limit)
        message.reply_text(f"Warning limit has been set to {limit}.")
        return (
            f"<b>{html.escape(chat.title)}:</b>\n"
            f"#SETWARNLIMIT\n"
            f"<b>Admin:</b> {admin.mention_html()}\n"
            f"<b>Limit:</b> {limit}"
        )
    except Exception as e:
        message.reply_text(f"Error setting warning limit: {e}")
        return f"ERROR: {e}"

@loggable
def set_warn_mode_cmd(update: Update, context: CallbackContext) -> str:
    args = context.args
    message = update.effective_message
    chat = update.effective_chat
    admin = update.effective_user

    if not is_user_admin(chat, admin.id):
        message.reply_text("You need to be an admin to set the warning mode.")
        return ""

    if not args or args[0].lower() not in ["soft", "hard"]:
        message.reply_text("Please specify the mode: 'soft' or 'hard' (e.g., /setwarnmode soft).")
        return ""

    mode_str = args[0].lower()
    soft_warn_bool = mode_str == "soft"

    try:
        sql.set_warn_strength(chat.id, soft_warn_bool)
        message.reply_text(f"Warning mode has been set to <b>{mode_str}</b>.", parse_mode=ParseMode.HTML)
        return (
            f"<b>{html.escape(chat.title)}:</b>\n"
            f"#SETWARNMODE\n"
            f"<b>Admin:</b> {admin.mention_html()}\n"
            f"<b>Mode:</b> {mode_str}"
        )
    except Exception as e:
        message.reply_text(f"Error setting warning mode: {e}")
        return f"ERROR: {e}"

# Handlers
WARN_HANDLER = CommandHandler(["warn", "w"], warn_user_cmd, filters=Filters.chat_type.groups, run_async=True)
RESET_WARN_HANDLER = CommandHandler(["resetwarns", "rw"], reset_warnings_cmd, filters=Filters.chat_type.groups, run_async=True)
GET_WARN_HANDLER = CommandHandler("warnings", get_warnings_cmd, filters=Filters.chat_type.groups, run_async=True)
SET_WARN_LIMIT_HANDLER = CommandHandler("setwarnlimit", set_warn_limit_cmd, filters=Filters.chat_type.groups, run_async=True)
SET_WARN_MODE_HANDLER = CommandHandler("setwarnmode", set_warn_mode_cmd, filters=Filters.chat_type.groups, run_async=True)


dispatcher.add_handler(WARN_HANDLER, WARN_HANDLER_GROUP)
dispatcher.add_handler(RESET_WARN_HANDLER, DEL_WARN_HANDLER_GROUP)
dispatcher.add_handler(GET_WARN_HANDLER, GET_WARN_HANDLER_GROUP)
dispatcher.add_handler(SET_WARN_LIMIT_HANDLER, SETTINGS_HANDLER_GROUP)
dispatcher.add_handler(SET_WARN_MODE_HANDLER, SETTINGS_HANDLER_GROUP)

__mod_name__ = "Warnings"
__handlers__ = [
    (WARN_HANDLER, WARN_HANDLER_GROUP),
    (RESET_WARN_HANDLER, DEL_WARN_HANDLER_GROUP), # DEL_WARN_HANDLER_GROUP is 10, same as WARN_HANDLER_GROUP
    (GET_WARN_HANDLER, GET_WARN_HANDLER_GROUP),   # GET_WARN_HANDLER_GROUP is 10, same as WARN_HANDLER_GROUP
    (SET_WARN_LIMIT_HANDLER, SETTINGS_HANDLER_GROUP),
    (SET_WARN_MODE_HANDLER, SETTINGS_HANDLER_GROUP),
]

__help__ = """
**User Commands:**
- /warnings <userhandle/id>: Get a user's warnings and reasons.

**Admin Commands:**
- /warn or /w <userhandle/id> <reason>: Warn a user. If the user reaches the warn limit, they will be kicked (unless in soft mode).
- /resetwarns or /rw <userhandle/id>: Reset all warnings for a user.
- /setwarnlimit <number>: Set the maximum number of warnings (e.g., 3) before action is taken. Minimum 1.
- /setwarnmode <soft/hard>: Set the warning mode for the chat.
    - `soft`: Users are notified upon reaching the warn limit, but no automated action is taken.
    - `hard`: Users are automatically kicked from the chat upon reaching the warn limit.
"""
