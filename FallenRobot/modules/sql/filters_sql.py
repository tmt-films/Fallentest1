import threading
from sqlalchemy import Column, String, UnicodeText, distinct, func
from FallenRobot.modules.sql import BASE, SESSION

class WordFilters(BASE):
    __tablename__ = "word_filters"
    chat_id = Column(String(14), primary_key=True, nullable=False)
    keyword = Column(UnicodeText, primary_key=True, nullable=False)

    def __init__(self, chat_id, keyword):
        self.chat_id = str(chat_id)
        self.keyword = keyword

    def __repr__(self):
        return "<Filter '{}' for chat {}>".format(self.keyword, self.chat_id)

WordFilters.__table__.create(checkfirst=True)

FILTER_LOCK = threading.RLock()

def add_filter(chat_id, keyword):
    with FILTER_LOCK:
        chat_filter = WordFilters(str(chat_id), keyword)
        SESSION.merge(chat_filter)  # merge to avoid duplicate key issues if it already exists
        SESSION.commit()

def remove_filter(chat_id, keyword):
    with FILTER_LOCK:
        chat_filter = SESSION.query(WordFilters).get((str(chat_id), keyword))
        if chat_filter:
            SESSION.delete(chat_filter)
            SESSION.commit()
            return True
        return False

def get_chat_filters(chat_id):
    try:
        return (
            SESSION.query(WordFilters.keyword)
            .filter(WordFilters.chat_id == str(chat_id))
            .all()
        )
    finally:
        SESSION.close()

def get_all_filters():
    try:
        return SESSION.query(WordFilters).all()
    finally:
        SESSION.close()

def num_filters():
    try:
        return SESSION.query(WordFilters).count()
    finally:
        SESSION.close()

def num_filter_chats():
    try:
        return SESSION.query(func.count(distinct(WordFilters.chat_id))).scalar()
    finally:
        SESSION.close()

def migrate_chat(old_chat_id, new_chat_id):
    with FILTER_LOCK:
        SESSION.query(WordFilters).filter(WordFilters.chat_id == str(old_chat_id)).update(
            {WordFilters.chat_id: str(new_chat_id)}, synchronize_session="fetch"
        )
        SESSION.commit()
