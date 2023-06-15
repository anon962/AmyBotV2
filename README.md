Rewrite of https://github.com/anon962/AmyBot

---

### Description

This repo contains (1) an API for HV auction / lottery data and (2) a discord bot that queries this API.

Live demo: https://hvdata.gisadan.dev/docs/

### Setup

1. Create a `/src/config/secrets.toml` file using [secrets_example.toml](https://github.com/anon962/AmyBotV2/blob/master/src/config/secrets_example.toml).
2. (optional) Edit the other config files in `/src/config/` as necessary.
3. Install dependencies `pip install -r requirements.txt`
4. Start server `python3 run_server.py` and discord bot `python3 run_bot.py`. (Or just `bash launch.sh`)

See the [demo site](https://hvdata.gisadan.dev/docs/) or [server.py](https://github.com/anon962/AmyBotV2/blob/master/src/classes/core/server/server.py) for details about the API.

### Database

The database is not automatically populated. It's recommended that you clone the existing DB instead of hitting up the HV / reasoningtheory servers from scratch.

`curl https://hvdata.gisadan.dev/export/sqlite | sqlite3 ./src/data/db.sqlite`

But you can manually update it by running:
- `export PYTHONPATH=/path/to/AmyBotV2/src; python3 /path/to/AmyBotV2/src/classes/scrapers/super_scraper.py`
- `export PYTHONPATH=/path/to/AmyBotV2/src; python3 /path/to/AmyBotV2/src/classes/scrapers/kedama_scraper.py`
- `export PYTHONPATH=/path/to/AmyBotV2/src; python3 /path/to/AmyBotV2/src/classes/scrapers/lottery_scraper.py`

This data is also available in JSON format:

`curl https://hvdata.gisadan.dev/export/json | jq`

### Samples

<blockquote><details>
<summary>Searching auction data</summary>
<img src="https://user-images.githubusercontent.com/24236225/211687135-d9b826ac-ab16-4c70-87f7-d04117ae51f9.png">
<img src="https://user-images.githubusercontent.com/24236225/211686727-276dae1b-f5f6-4afd-bbcc-78c8a9790a52.png">
</details></blockquote>
