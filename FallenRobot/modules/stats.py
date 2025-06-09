import html
from telegram import Update, ParseMode, TelegramError, Filters
from telegram.ext import CallbackContext, CommandHandler

from FallenRobot import dispatcher, LOGGER
from FallenRobot.modules.sql import stats_sql
from FallenRobot.modules.helper_funcs.chat_status import user_admin

STATS_CMD_HANDLER_GROUP = 12 # Example group

@user_admin
def chat_stats_command(update: Update, context: CallbackContext):
    chat = update.effective_chat
    chat_id_str = str(chat.id)
    chat_title = chat.title if chat.title else "this chat"

    try:
        total_messages = stats_sql.get_total_messages_in_chat(chat_id_str)
        unique_users = stats_sql.get_unique_users_count_in_chat(chat_id_str)
        top_posters_data = stats_sql.get_top_posters_in_chat(chat_id_str, limit=5)

        reply_message = f"📊 <b>Chat Statistics for {html.escape(chat_title)}</b>\n\n"
        reply_message += f"💬 Total Logged Messages: {total_messages}\n"
        reply_message += f"👥 Unique Users Logged: {unique_users}\n\n"

        if top_posters_data:
            reply_message += "🏆 <b>Top Posters:</b>\n"
            for i, (user_id, msg_count) in enumerate(top_posters_data):
                user_display_name = f"User ID {user_id}" # Default
                try:
                    member = context.bot.get_chat_member(chat_id_str, user_id)
                    if member and member.user:
                        user_display_name = member.user.mention_html() # Use mention_html for clickable link
                except TelegramError as e:
                    LOGGER.warning(f"Could not fetch member {user_id} for stats in chat {chat_id_str}: {e}")
                except Exception as e_gen: # Catch other potential errors like user not found after leaving
                    LOGGER.warning(f"Generic error fetching member {user_id} for stats in chat {chat_id_str}: {e_gen}")

                reply_message += f"  {i+1}. {user_display_name} ({msg_count} messages)\n"
        else:
            reply_message += "🏆 Top Posters: No activity logged yet or insufficient data.\n"

        update.effective_message.reply_text(reply_message, parse_mode=ParseMode.HTML)

    except Exception as e:
        LOGGER.error(f"Error generating chat stats for {chat_id_str}: {e}", exc_info=True)
        update.effective_message.reply_text("An error occurred while fetching chat statistics. Please try again later.")


STATS_CMD_HANDLER = CommandHandler(
    "stats",
    chat_stats_command,
    filters=Filters.chat_type.groups,
    run_async=True
)

dispatcher.add_handler(STATS_CMD_HANDLER, STATS_CMD_HANDLER_GROUP)

__mod_name__ = "Chat Statistics"
__help__ = """
Provides statistics about chat activity. Only available to admins.

*Admin Commands:*
  ❍ /stats: Shows chat statistics including total messages, unique users, and top posters.
    Note: Stats are based on messages logged since the bot was added and operational.
"""

__handlers__ = [(STATS_CMD_HANDLER, STATS_CMD_HANDLER_GROUP)]
```
