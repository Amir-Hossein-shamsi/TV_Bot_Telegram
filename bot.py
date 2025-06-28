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

# TV programs with emojis
TV_PROGRAMS: List[str] = [
    '🕮 Quran Match', 
    '📰 Turkish News', 
    '👨‍🍳 Cooking Show', 
    '⚽ Sports Highlights'
]

# Ensure assets directory exists
os.makedirs(ASSETS_DIR, exist_ok=True)

# Logging config
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Elasticsearch client
es = Elasticsearch(hosts=[{'host': ES_HOST, 'port': ES_PORT, 'scheme': 'http'}])

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

# Enhanced text resources with emojis and formatting
TEXTS = {
    'welcome': (
        "🌟 *Welcome to TV Critic Hub!* 🌟\n\n"
        "Join our community of media critics or participate in exciting game shows!\n"
        "Choose an option below to get started:"
    ),
    'critics': '🎬 Become a TV Critic',
    'game': '🎮 Register for Game Show',
    'first_name': "📝 *First Name:*\nPlease enter your first name:",
    'last_name': "✅ *First name saved!*\n\n📝 *Last Name:*\nPlease enter your last name:",
    'phone': "✅ *Last name saved!*\n\n📱 *Phone Number:*\nPlease share your contact number:",
    'registered': (
        "🎉 *Registration Complete!*\n\n"
        "You're now a certified TV critic! Let's review some shows.\n"
        "Select a program to critique:"
    ),
    'pick_program': "📺 *Select a TV Program:*\nChoose which show you'd like to review:",
    'send_critique': (
        "✍️ *Submit Your Critique*\n\n"
        "Share your thoughts about *{program}*!\n"
        "You can either:\n"
        "• Type your review as text\n"
        "• Or record a voice message\n\n"
        "We value your opinion! 🎤"
    ),
    'saved': "✅ *Critique Received!*",
    'show_id': "🆔 Your unique critique ID: `{critique_id}`",
    'cancelled': "❌ *Operation cancelled.*",
    'error': "⚠️ *Oops! Something went wrong.*\nPlease try again later.",
    'text_voice': "❌ Please send either text or voice only.",
    'register_first': (
        "🔒 *Registration Required*\n\n"
        "Please complete your critic registration first!\n"
        "Use /start to begin."
    ),
    'game_registered': "🎉 *Game Registration Complete!*\n\nYou're now entered in our weekly drawing!",
    'player_name': "👤 *Player Name:*\nEnter your display name for the game:",
    'cancel': "🚫 Cancel"
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

async def send(update: Update, text: str, reply_markup=None, parse_mode='Markdown'):
    """Smart send: edits if callback, replies otherwise."""
    if update.callback_query:
        cq = update.callback_query
        await cq.answer()
        try:
            await cq.edit_message_text(
                text, 
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        except:
            await cq.message.reply_text(
                text, 
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
    else:
        await update.message.reply_text(
            text, 
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )


def create_keyboard(options: List[str], prefix: str = '', cols: int = 2, cancel_btn: bool = False) -> InlineKeyboardMarkup:
    """Create a formatted keyboard with optional cancel button."""
    buttons = []
    for i, opt in enumerate(options):
        buttons.append(InlineKeyboardButton(opt, callback_data=f"{prefix}{i}"))
    
    # Arrange buttons in columns
    keyboard = [buttons[i:i+cols] for i in range(0, len(buttons), cols)]
    
    # Add cancel button if needed
    if cancel_btn:
        keyboard.append([InlineKeyboardButton(TEXTS['cancel'], callback_data='cancel')])
    
    return InlineKeyboardMarkup(keyboard)


# Handlers
@catch_errors
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Send welcome message with main menu options."""
    opts = [TEXTS['critics'], TEXTS['game']]
    await send(
        update, 
        TEXTS['welcome'], 
        reply_markup=create_keyboard(opts, cols=1)
    )
    return MAIN_MENU

@catch_errors
async def main_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle main menu selection."""
    data = update.callback_query.data
    
    if data == 'cancel':
        await send(update, TEXTS['cancelled'])
        return await start(update, ctx)
    
    if data == '0':  # Critics
        uid = update.effective_user.id
        if get_doc('critics', uid):
            await send(
                update, 
                TEXTS['pick_program'], 
                reply_markup=create_keyboard(TV_PROGRAMS, prefix='prog_', cols=2, cancel_btn=True)
            )
            return SELECT_PROGRAM
            
        ctx.user_data.clear()
        ctx.user_data.update({'step': 'first', 'uid': uid})
        await send(update, TEXTS['first_name'])
        return REGISTER_CRITIC
        
    if data == '1':  # Game
        ctx.user_data.clear()
        ctx.user_data.update({'step': 'player_name', 'uid': update.effective_user.id})
        await send(update, TEXTS['player_name'])
        return REGISTER_GAME
        
    if data.startswith('prog_'):
        return await select_program(update, ctx)
        
    return MAIN_MENU

@catch_errors
async def register_critic(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Step-by-step critic registration."""
    if update.message.text.strip().lower() == '/cancel':
        await send(update, TEXTS['cancelled'])
        return await start(update, ctx)
        
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
        
    # Phone step
    doc = {
        'user_id': ctx.user_data['uid'],
        'first_name': ctx.user_data['first'],
        'last_name': ctx.user_data['last'],
        'phone': text,
        'timestamp': datetime.utcnow()
    }
    idx_doc('critics', doc, ctx.user_data['uid'])
    await send(
        update, 
        TEXTS['registered'], 
        reply_markup=create_keyboard(TV_PROGRAMS, prefix='prog_', cols=2, cancel_btn=True)
    )
    return SELECT_PROGRAM

@catch_errors
async def select_program(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle program selection for critique."""
    if update.callback_query.data == 'cancel':
        await send(update, TEXTS['cancelled'])
        return await start(update, ctx)
        
    idx = int(update.callback_query.data.replace('prog_', ''))
    prog = TV_PROGRAMS[idx].split(' ', 1)[1]  # Remove emoji for storage
    ctx.user_data['program'] = prog
    await send(update, TEXTS['send_critique'].format(program=TV_PROGRAMS[idx]))
    return SUBMIT_CRITIQUE

@catch_errors
async def submit_critique(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle critique submission (text or voice)."""
    uid = update.effective_user.id
    prog = ctx.user_data.get('program')
    
    if not prog or not get_doc('critics', uid):
        await send(update, TEXTS['register_first'])
        return await start(update, ctx)

    # Create program folder
    prog_folder = os.path.join(ASSETS_DIR, prog.replace(' ', '_'))
    os.makedirs(prog_folder, exist_ok=True)

    # Generate received ID
    rec_id = uuid.uuid4().hex[:8].upper()
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
    await send(update, f"{TEXTS['saved']}\n\n{TEXTS['show_id'].format(critique_id=rec_id)}")
    ctx.user_data.pop('program', None)
    return await start(update, ctx)

@catch_errors
async def register_game(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle game registration."""
    if update.message.text.strip().lower() == '/cancel':
        await send(update, TEXTS['cancelled'])
        return await start(update, ctx)
        
    player_name = update.message.text.strip()
    doc = {
        'user_id': update.effective_user.id,
        'player_name': player_name,
        'registration_date': datetime.utcnow()
    }
    idx_doc('game', doc)
    await send(update, TEXTS['game_registered'])
    return await start(update, ctx)

@catch_errors
async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel any ongoing operation."""
    await send(update, TEXTS['cancelled'])
    return await start(update, ctx)

if __name__ == '__main__':
    ensure_indices()
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler with cancel support
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [CallbackQueryHandler(main_menu)],
            REGISTER_CRITIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, register_critic),
                CommandHandler('cancel', cancel)
            ],
            SELECT_PROGRAM: [CallbackQueryHandler(select_program)],
            SUBMIT_CRITIQUE: [
                MessageHandler(filters.TEXT | filters.VOICE, submit_critique),
                CommandHandler('cancel', cancel)
            ],
            REGISTER_GAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, register_game),
                CommandHandler('cancel', cancel)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    
    app.add_handler(conv)
    app.run_polling()