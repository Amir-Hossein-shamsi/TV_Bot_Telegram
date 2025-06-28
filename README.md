# TV Channel Telegram Bot

A Telegram bot that allows users to register as TV critics, submit text or voice critiques for selected TV programs, and stores all data in Elasticsearch. It also supports a simple “game registration” flow. An HTTP API (FastAPI) is also provided for querying critics and critiques.

---

## Features

- **Critics Registration**  
  Collects first name, last name, and phone number.  
  Stores critic profiles in Elasticsearch (`telegram_critics` index).

- **Submit Critiques**  
  Users select a TV program from a predefined list, then submit text or voice critiques.  
  Critiques are saved to disk (under `assets/`), and metadata is indexed in Elasticsearch (`telegram_critiques` index), including text excerpts and voice duration.

- **Game Registration**  
  Users can register for a game show by providing a display name.  
  Registrations are stored in Elasticsearch (`game_registrants` index).

- **Error Handling**  
  All handlers are wrapped with a decorator to catch and report unexpected errors.

- **REST API**  
  FastAPI server provides endpoints to list critics, critiques, game registrants, and search across all indices.

---

## Prerequisites

- Python 3.12+  
- Elasticsearch 7.x or 8.x running and accessible  
- A Telegram Bot Token  

---

## Installation

1. **Clone the repo**  
   ```bash
   git clone https://github.com/your-username/tv-channel-bot.git
   cd tv-channel-bot
   ```

2. **Install dependencies**  
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**  
   - Copy `.env.exampel` to `.env` and fill in your `TELEGRAM_BOT_TOKEN` and (optionally) `GroupChat_ID`.
   - Optionally set `ELASTICSEARCH_HOST`, `ELASTICSEARCH_PORT`, and `ASSETS_DIR` in `.env`.

4. **Start Elasticsearch**  
   - You can use Docker Compose:
     ```bash
     docker-compose up -d
     ```

5. **Run the bot**  
   ```bash
   python bot.py
   ```

6. **Run the API server**  
   ```bash
   python api.py
   ```
   The API will be available at `http://localhost:8000`.

---

## Usage

- Start the bot in Telegram and follow the prompts to register as a critic or for the game show.
- Submit critiques as text or voice for the available TV programs:
  - 🕮 Quran Match
  - 📰 Turkish News
  - 👨‍🍳 Cooking Show
  - ⚽ Sports Highlights

---

## API Endpoints

- `GET /indices` — List available indices
- `GET /critics` — List all critics
- `GET /critiques` — List all critiques
- `GET /game-registrants` — List all game registrants
- `GET /critiques/by-program/{program}` — List critiques for a specific TV program
- `GET /critiques/by-user/{user_id}` — List critiques by user
- `GET /search?query=...` — Full-text search across all indices

See [api.py](api.py) for details.

---

## File Structure

- [`bot.py`](bot.py): Main Telegram bot logic
- [`api.py`](api.py): FastAPI server for querying Elasticsearch
- [`assets/`](assets/): Saved critiques (text and voice)
- [`docker-compose.yml`](docker-compose.yml): For running Elasticsearch via Docker
- [`requirements.txt`](requirements.txt): Python dependencies

---

##