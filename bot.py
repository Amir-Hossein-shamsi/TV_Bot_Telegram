import os
import logging
import uuid
from datetime import datetime
from functools import wraps
from typing import Dict, Optional, Union, List

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)
from elasticsearch import Elasticsearch, NotFoundError

# Load configuration
load_dotenv()
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ES_HOST = os.getenv('ELASTICSEARCH_HOST', 'localhost')
ES_PORT = int(os.getenv('ELASTICSEARCH_PORT', 9200))
ASSETS_DIR = os.getenv('ASSETS_DIR', 'assets')

# TV programs
TV_PROGRAMS: List[str] = ['Love Island', 'Turkish News', 'Cooking Show', 'Sports Highlights']

# Ensure assets directory exists
os.makedirs(ASSETS_DIR, exist_ok=True)

# Logging config
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Elasticsearch client
es = Elasticsearch(hosts=[{'host': ES_HOST, 'port': ES_PORT,'scheme':'http'}])

# States
MAIN_MENU, REGISTER_CRITIC, SELECT_PROGRAM, SUBMIT_CRITIQUE, REGISTER_GAME = range(5)

# Index names
doc_indices = {
    'critics': 'telegram_critics',
    'critiques': 'telegram_critiques',
    'game': 'game_registrants'
}

# Index mappings
INDEX_MAPPINGS = {
    'critics': {
        'properties': {
            'user_id': {'type': 'long'},
            'first_name': {'type': 'text'},
            'last_name': {'type': 'text'},
            'phone': {'type': 'keyword'},
            'timestamp': {'type': 'date'}
        }
    },
    'critiques': {
        'properties': {
            'user_id': {'type': 'long'},
            'program': {'type': 'keyword'},
            'received_id': {'type': 'keyword'},
            'file_path': {'type': 'keyword'},
            'timestamp': {'type': 'date'},
            'content_type': {'type': 'keyword'},
            'text_content': {'type': 'text'},
            'voice_duration': {'type': 'integer'}
        }
    },
    'game': {
        'properties': {
            'user_id': {'type': 'long'},
            'player_name': {'type': 'text'},
            'registration_date': {'type': 'date'}
        }
    }
}

# Text resources
TEXTS = {
    'welcome': "🏆 Welcome to *** TV Channel Bot! Choose:",
    'critics': 'Critics Section',
    'game': 'Game Registration',
    'first_name': "📝 Send FIRST name:",
    'last_name': "✅ First saved! Send LAST name:",
    'phone': "✅ Last saved! Send PHONE number:",
    'registered': "🎉 Registered! Now pick a program:",
    'pick_program': "🔍 Select a TV program to critique:",
    'send_critique': "✍️ Send critique text or voice:",
    'saved': "✅ Critique received!",
    'show_id': "🎫 Your critique ID is",
    'cancelled': "❌ Operation cancelled.",
    'error': "❌ Unexpected error, try later.",
    'text_voice': "❌ Send text or voice only.",
    'register_first': "❌ Please /start to register first.",
}

# Helpers

def ensure_indices():
    """Ensure Elasticsearch indices exist with proper mappings."""
    for key, index in doc_indices.items():
        if not es.indices.exists(index=index):
            body = {'mappings': INDEX_MAPPINGS[key]}
            es.indices.create(index=index, body=body)
            logger.info(f"Created index {index} with mappings.")


def get_doc(kind: str, id: Union[int, str]) -> Optional[Dict]:
    try:
        return es.get(index=doc_indices[kind], id=str(id))['_source']
    except NotFoundError:
        return None
    except Exception as exc:
        logger.error(f"Error fetching {kind}: {exc}")
        return None


def idx_doc(kind: str, doc: Dict, id: Optional[Union[int, str]] = None):
    try:
        es.index(index=doc_indices[kind], id=str(id) if id else None, document=doc)
    except Exception as exc:
        logger.error(f"Error indexing {kind}: {exc}")


def catch_errors(f):
    @wraps(f)
    async def wrapped(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        try:
            return await f(update, ctx)
        except Exception as exc:
            logger.exception(f"Handler {f.__name__} error: {exc}")
            await send(update, TEXTS['error'])
            return ConversationHandler.END
    return wrapped

async def send(update: Update, text: str, reply_markup=None):
    """Smart send: edits if callback, replies otherwise."""
    if update.callback_query:
        cq = update.callback_query
        await cq.answer()
        try:
            await cq.edit_message_text(text, reply_markup=reply_markup)
        except:
            await cq.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)


def kb(options: List[str], prefix: str = '') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(opt, callback_data=f"{prefix}{i}")] for i, opt in enumerate(options)]
    )

# Handlers
@catch_errors
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    opts = [TEXTS['critics'], TEXTS['game']]
    await send(update, TEXTS['welcome'], reply_markup=kb(opts))
    return MAIN_MENU

@catch_errors
async def main_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    data = update.callback_query.data
    if data == '0':  # Critics
        uid = update.effective_user.id
        if get_doc('critics', uid):
            await send(update, TEXTS['pick_program'], reply_markup=kb(TV_PROGRAMS, prefix='prog'))
            return SELECT_PROGRAM
        ctx.user_data.clear()
        ctx.user_data.update({'step': 'first', 'uid': uid})
        await send(update, TEXTS['first_name'])
        return REGISTER_CRITIC
    if data == '1':  # Game
        await send(update, TEXTS['game'])
        return REGISTER_GAME
    if data.startswith('prog'):
        return await select_program(update, ctx)
    return MAIN_MENU

@catch_errors
async def register_critic(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    step = ctx.user_data['step']
    if step == 'first':
        ctx.user_data.update({'first': text, 'step': 'last'})
        await send(update, TEXTS['last_name'])
        return REGISTER_CRITIC
    if step == 'last':
        ctx.user_data.update({'last': text, 'step': 'phone'})
        await send(update, TEXTS['phone'])
        return REGISTER_CRITIC
    # phone step
    doc = {
        'user_id': ctx.user_data['uid'],
        'first_name': ctx.user_data['first'],
        'last_name': ctx.user_data['last'],
        'phone': text,
        'timestamp': datetime.utcnow()
    }
    idx_doc('critics', doc, ctx.user_data['uid'])
    await send(update, TEXTS['registered'], reply_markup=kb(TV_PROGRAMS, prefix='prog'))
    return SELECT_PROGRAM

@catch_errors
async def select_program(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    idx = int(update.callback_query.data.replace('prog', ''))
    prog = TV_PROGRAMS[idx]
    ctx.user_data['program'] = prog
    await send(update, f"{TEXTS['send_critique']}\nProgram: {prog}")
    return SUBMIT_CRITIQUE

@catch_errors
async def submit_critique(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    prog = ctx.user_data.get('program')
    if not prog or not get_doc('critics', uid):
        await send(update, TEXTS['register_first'])
        return await start(update, ctx)

    # Create program folder
    prog_folder = os.path.join(ASSETS_DIR, prog.replace(' ', '_'))
    os.makedirs(prog_folder, exist_ok=True)

    # Generate received ID
    rec_id = uuid.uuid4().hex
    now = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

    # Save content
    if update.message.text:
        content = update.message.text
        fname = f"{rec_id}.txt"
        path = os.path.join(prog_folder, fname)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        doc = {
            'user_id': uid,
            'program': prog,
            'received_id': rec_id,
            'file_path': path,
            'timestamp': datetime.utcnow(),
            'content_type': 'text',
            'text_content': content[:1000],
            'voice_duration': None
        }
    elif update.message.voice:
        vf = update.message.voice
        file = await ctx.bot.get_file(vf.file_id)
        fname = f"{rec_id}.ogg"
        path = os.path.join(prog_folder, fname)
        await file.download_to_drive(path)
        doc = {
            'user_id': uid,
            'program': prog,
            'received_id': rec_id,
            'file_path': path,
            'timestamp': datetime.utcnow(),
            'content_type': 'voice',
            'text_content': None,
            'voice_duration': vf.duration
        }
    else:
        await send(update, TEXTS['text_voice'])
        return SUBMIT_CRITIQUE

    # Index and respond
    idx_doc('critiques', doc)
    await send(update, f"{TEXTS['saved']}\n{TEXTS['show_id']} {rec_id}")
    ctx.user_data.pop('program', None)
    return MAIN_MENU

if __name__ == '__main__':
    ensure_indices()
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [CallbackQueryHandler(main_menu)],
            REGISTER_CRITIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_critic)],
            SELECT_PROGRAM: [CallbackQueryHandler(select_program)],
            SUBMIT_CRITIQUE: [MessageHandler(filters.TEXT | filters.VOICE, submit_critique)],
            REGISTER_GAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_game := register_critic)],
        },
        fallbacks=[CommandHandler('cancel', cancel := start)]
    )
    app.add_handler(conv)
    app.run_polling()
