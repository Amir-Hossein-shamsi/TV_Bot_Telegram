# TV Channel Telegram Bot

A Telegram bot that allows users to register as TV critics, submit text or voice critiques for selected TV programs, and stores all data in Elasticsearch. It also supports a simple “game registration” flow.

---

## Features

- **Critics Registration**  
  Collects first name, last name, and phone number.  
  Stores critic profiles in Elasticsearch.

- **Submit Critiques**  
  Users select a TV program from a predefined list, then submit text or voice critiques.  
  Critiques are saved to disk (under `assets/`), and metadata is indexed in Elasticsearch (including text excerpts and voice duration).

- **Game Registration**  
  A placeholder flow that can be extended for game or contest sign-ups.

- **Error Handling**  
  All handlers are wrapped with a decorator to catch and report unexpected errors.

---

## Prerequisites

- Python 3.8+  
- Elasticsearch 7.x or 8.x running and accessible  
- A Telegram Bot Token  

---

## Installation

1. **Clone the repo**  
   ```bash
   git clone https://github.com/your-username/tv-channel-bot.git
   cd tv-channel-bot
