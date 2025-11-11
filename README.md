# Auction_bot
💰 Live FIFA Auction Bot 💰  I run your league's auction with real-time bidding and budget tracking.  • Live Countdown Auctions: 5-second timer on all bids! • Draft Mode: A special draft for managers who run out of money. • Steal Mechanic: Steal other managers' draft picks!  Use /status to see the board and /nominate to start.
# FIFA Auction Discord Bot (v3.0 - Auto-Auction)

This bot manages a live, automated FIFA player auction. The bot presents players one-by-one in tiered OVR groups, and managers bid in real-time by just typing numbers in the chat.

## Setup Instructions

1.  **Create a Bot Application:**
    * Go to the [Discord Developer Portal](https://discord.com/developers/applications).
    * Click "New Application".
    * Go to the "Bot" tab and click "Add Bot".
    * Copy the bot's **TOKEN**.
2.  **Store Your Token:**
    * Paste your token into the `.env` file, replacing `YOUR_BOT_TOKEN_HERE`.
3.  **Enable Intents:**
    * In the "Bot" tab, scroll down and enable **ALL 3 Privileged Gateway Intents**:
        * `PRESENCE INTENT`
        * `SERVER MEMBERS INTENT`
        * `MESSAGE CONTENT INTENT`
4.  **Install Libraries:**
    * `pip install discord.py python-dotenv`
5.  **Run the Bot:**
    * Place all the files in the same folder.
    * Run the bot: `python bot.py`
6.  **Invite the Bot:**
    * In "OAuth2" -> "URL Generator", select `bot` and `applications.commands`.
    * Grant `Send Messages`, `Read Message History`, and `Embed Links` permissions.
    * Copy the generated URL to invite the bot to your server.

## Auction Flow (How to Use)

1.  **Setup (Admin):**
    * Use `/reset` to clear any old data.
    * Use `/addmanager "[Name]" [budget_in_M]` to add all managers. (e.g., `/addmanager "Jai Kinner" 900`).
    * **Crucially, make sure every manager's "Name" here matches their Discord Display Name *exactly***.
    * Use `/setcap [number]` if you want a cap other than 18.
2.  **Player Database (Admin):**
    * The `player_database.json` file is pre-loaded with 163 players and their OVRs. You can add/edit with `/editplayer`.
3.  **Retention Phase (Admin):**
    * Use `/retain "[Player Name]" "[Manager Name]"` for any retained players. This removes them from the auction queue.
4.  **Start the Auction (Admin):**
    * Type `/start`.
    * The bot will build the tiered, shuffled queue (86+, 83-85, <=82) and announce the first player.
5.  **Auto-Auction Mode (Public):**
    * The bot presents a player and their starting bid.
    * Any manager can bid by typing a number (in millions) in the chat (e.g., `150`).
    * Each new high bid resets a **5-second countdown**.
    * If the countdown finishes, the player is sold.
    * The bot **automatically** announces the next player from the queue.
    * Admins can use `/pause`, `/resume`, or `/unsold` to control the auction.
6.  **Draft Mode (Automatic):**
    * The bot will **automatically** start draft mode when 3 or more managers have $0.
    * The rest of the flow (`/draft`, `/steal`) remains the same.

## Full Command List

### Admin Commands
* `/reset`
* `/start` (Starts the new auto-auction)
* `/addmanager "[Name]" [budget_in_M]`
* `/removemanager "[Name]"`
* `/setbudget "[Name]" [budget_in_M]`
* `/setcap [cap_number]`
* `/retain "[Player Name]" "[Manager Name]"`
* `/editplayer "[Player Name]" "[Team]" [OVR] [base_price_in_M]`
* `/pause`
* `/resume`
* `/unsold` (Skips the current player and calls the next)
* `/startdraft` (Manually starts the draft)
* `/undo` (Reverts the last sale/draft/retention)

### Public Commands
* **(BIDDING)**: Just type a number in the chat (e.g., `120`)
* `/draft "[Player Name]"` (Drafts a player on your turn)
* `/steal` (Steals the currently drafted player)
* `/status` (Shows the main auction board)
* `/team "[Manager Name]"` (Shows a manager's full squad)
* `/listplayers` (Lists all available players in the database)
* `/playerinfo "[Player Name]"` (Gets info for one player)
