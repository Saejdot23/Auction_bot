# Auction_bot
💰 Live FIFA Auction Bot 💰  I run your league's auction with real-time bidding and budget tracking.  • Live Countdown Auctions: 5-second timer on all bids! • Draft Mode: A special draft for managers who run out of money. • Steal Mechanic: Steal other managers' draft picks!  Use /status to see the board and /nominate to start.
# FIFA Auction Discord Bot (v2.0 - Live Auction)

This bot manages a live, interactive FIFA player auction with real-time bidding, a player database, and a full draft mode.

## Setup Instructions

1.  **Create a Bot Application:**
    * Go to the [Discord Developer Portal](https://discord.com/developers/applications).
    * Click "New Application".
    * Go to the "Bot" tab and click "Add Bot".
    * Copy the bot's **TOKEN**.
2.  **Store Your Token:**
    * Paste your token into the `.env` file, replacing `YOUR_BOT_TOKEN_HERE`. **Never share this token!**
3.  **Enable Intents:**
    * In the "Bot" tab, scroll down and enable the **"Message Content Intent"**.
4.  **Install Libraries:**
    * You need Python 3.8 or newer.
    * Install the required libraries:
        ```sh
        pip install discord.py
        pip install python-dotenv
        ```
5.  **Run the Bot:**
    * Place all the files (`bot.py`, `auction_data.json`, `player_database.json`, `.env`, `README.md`) in the same folder.
    * Run the bot from your terminal:
        ```sh
        python bot.py
        ```
6.  **Invite the Bot:**
    * In the Developer Portal, go to "OAuth2" -> "URL Generator".
    * Select the `bot` and `applications.commands` scopes.
    * In "Bot Permissions", select `Send Messages`, `Read Message History`, and `Embed Links`.
    * Copy the generated URL and paste it into your browser to invite the bot to your server.

## Auction Flow (How to Use)

1.  **Setup (Admin):**
    * Use `/reset` to clear any old data.
    * Use `/addmanager "[Name]" [budget_in_M]` to add all your managers. (e.g., `/addmanager "Jai Kinner" 900`).
    * Use `/setcap [number]` if you want a cap other than 18.
2.  **Player Database (Admin):**
    * The `player_database.json` file is already pre-loaded with 127 players. You can add or edit players using `/editplayer "[Name]" "[Team]" [base_price_in_M]`.
3.  **Retention Phase (Admin):**
    * Use `/retain "[Player Name]" "[Manager Name]"` for any retained players. This will also remove them from the nomination pool.
4.  **Auction Mode (Admin/Public):**
    * Any user nominates a player with `/nominate "[Player Name]"`.
    * The bot announces the player and the starting bid (from the database).
    * Anyone can bid using `/bid [amount_in_M]`.
    * Each new high bid resets a **5-second countdown**.
    * If the countdown finishes, the player is sold to the last bidder.
    * Admins can use `/pause`, `/resume`, or `/unsold` to control the auction.
5.  **Draft Mode (Automatic/Public):**
    * The bot will **automatically** start draft mode when 3 or more managers have $0.
    * The bot announces the draft order and who is on the clock.
    * The drafting manager uses `/draft "[Player Name]"`.
    * The bot announces the player and the "steal price" (from the database).
    * A **15-second steal countdown** begins.
    * Any manager *with enough money* can use `/steal`.
    * If stolen, a **live auction** begins for that player (starting at the steal price).
    * If not stolen, the player joins the drafting manager's team for free.

## Full Command List

### Admin Commands
* `/reset`
* `/addmanager "[Name]" [budget_in_M]`
* `/removemanager "[Name]"`
* `/setbudget "[Name]" [budget_in_M]`
* `/setcap [cap_number]`
* `/retain "[Player Name]" "[Manager Name]"`
* `/editplayer "[Player Name]" "[Team]" [base_price_in_M]`
* `/pause`
* `/resume`
* `/unsold`
* `/startdraft` (Manually starts the draft)
* `/undo` (Reverts the last sale/draft/retention)

### Public Commands
* `/nominate "[Player Name]"` (Starts an auction)
* `/bid [amount_in_M]` (Bids on a player)
* `/draft "[Player Name]"` (Drafts a player on your turn)
* `/steal` (Steals the currently drafted player)
* `/status` (Shows the main auction board)
* `/team "[Manager Name]"` (Shows a manager's full squad)
* `/listplayers` (Lists all available players in the database)
* `/playerinfo "[Player Name]"` (Gets info for one player)
