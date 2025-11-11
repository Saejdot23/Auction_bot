
### **Project Retrospective: FIFA Auction Discord Bot**

As the lead developer on this project, I took a complex, manual auction process and engineered it into a fully-featured, real-time Discord bot.

Here's a breakdown of the development lifecycle:

### Phase 1: Prototyping & Concept Validation

Before writing any code, I first needed to validate the core logic. I used a simple chat interface as a "manual prototype" to run two complete auction simulations. I defined the managers, their specific budgets (e.g., $750M for Sahej, $900M for Jai ), and the "Retain One Player" rule. This manual process was crucial, as it helped me finalize the rules, confirm the data requirements (player lists, ratings), and prove that the core concept was viable.

### Phase 2: Architecture & Feature Scoping

With the prototype validated, I moved on to designing the application's architecture. I decided a state-aware Python bot using the `discord.py` library was the right-call.

I scoped out the following key features to move it from a simple tracker to a full-fleged application:

1.  **Dynamic State:** The bot needed to be fully dynamic, allowing admins to add, remove, and manage managers and budgets via slash commands.
2.  **External JSON Database:** I architected the bot to run off two separate JSON files:
    * `player_database.json`: A comprehensive, editable database of all available players and their base prices.
    * `auction_data.json`: A live "save file" to track the auction's state, budgets, and rosters, ensuring no data is lost on restart.
3.  **Real-Time Bidding:** The core feature was a live auction. I designed the `/bid` command to trigger an `asyncio` task: a 5-second countdown that would reset on any new, valid bid.
4.  **Advanced Game Mode (Draft & Steal):** This was the most complex feature. I designed a system where the bot automatically detects when 3+ managers have $0, pauses the auction, and initiates a "Draft Mode." I then added a `/steal` mechanic to allow managers with remaining funds to interrupt a draft pick and trigger a new, live auction for that player.

### Phase 3: Development & Implementation

I wrote the application, splitting the logic into 5 core files in my VS Code project:

1.  **`bot.py`**: The main application script. I wrote all the slash commands, error handling, and the complex `asyncio` logic for the auction and steal countdowns.
2.  **`player_database.json`**: I compiled and pre-loaded this database with 127 players from our test data, assigning a `base_price` to each based on their rating.
3.  **`auction_data.json`**: The clean "save state" file.
4.  **`.env`**: A standard file to securely store my bot's token.
5.  **`README.md`**: I wrote the full documentation for setup, commands, and the auction flow.

### Phase 4: Deployment & Debugging

Once the core code was written, I began the deployment and testing phase.

1.  **Initial Setup:** I created the application in the Discord Developer Portal and structured the project in VS Code.
2.  **First Bug (Token Error):** On the first run, I immediately hit a `python-dotenv could not parse statement` error, which caused a `FATAL ERROR: DISCORD_TOKEN not found`. I traced this to a simple formatting issue in my `.env` file, which I debugged and fixed by ensuring the token was correctly encapsulated in quotes.
3.  **Second Bug (Intents Error):** After fixing the token, the script ran but immediately crashed with a `discord.errors.PrivilegedIntentsRequired` error. This was a classic deployment oversight. I knew this meant my bot didn't have the right permissions.
4.  **The Fix:** I went back to the Developer Portal, navigated to the "Bot" tab, and enabled the **"MESSAGE CONTENT INTENT"** and **"SERVER MEMBERS INTENT"** toggles. I also generated the correct OAuth2 URL with `bot` and `applications.commands` scopes.

### Phase 5: Final Launch

After fixing the intents, I ran `python bot.py` in my terminal. The bot successfully logged in, synced its slash commands, and appeared "Online" in my Discord server. The project was complete, and I successfully tested the first commands to launch the new auction season.
