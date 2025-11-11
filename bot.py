import discord
from discord.ext import commands
import json
import os
import shutil
from dotenv import load_dotenv
import asyncio
import random

# --- Bot Setup ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

# --- Auction Configuration ---
DATA_FILE = 'auction_data.json'
BACKUP_FILE = 'auction_data.backup.json'
PLAYER_DB_FILE = 'player_database.json'
DEFAULT_PLAYER_CAP = 18
BID_COUNTDOWN_SECONDS = 5  # Time for final countdown
STEAL_COUNTDOWN_SECONDS = 15 # Time to decide to steal

# --- Global State Variables ---
bot.current_auction_task = None
bot.current_steal_task = None

# --- Data Management Functions ---

def get_default_data():
    """Returns the default data structure for a new auction."""
    return {
        "managers": {},
        "player_cap": DEFAULT_PLAYER_CAP,
        "auction_state": "idle", # idle, bidding, drafting, paused
        "auction_queue": [],     # NEW: List of player keys to auction
        "auction_queue_index": 0,# NEW: Current position in the queue
        "on_the_block": None,    # { "name": "Player", "base_price": 10, "ovr": 88 }
        "current_bid": 0,
        "current_bidder": None,  # Manager key
        "draft_order": [],
        "draft_pick_index": 0
    }

def load_data(file):
    """Loads a JSON file."""
    if not os.path.exists(file):
        if file == DATA_FILE:
            data = get_default_data()
        elif file == PLAYER_DB_FILE:
            data = {} 
        save_data(data, file)
        return data
    try:
        with open(file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return get_default_data() if file == DATA_FILE else {}

def save_data(data, file):
    """Saves data to a JSON file."""
    if file == DATA_FILE:
        if os.path.exists(DATA_FILE):
            shutil.copy(DATA_FILE, BACKUP_FILE)
    
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# --- Helper Functions ---

def get_player_count(manager_data):
    """Calculates the total number of players for a manager."""
    return len(manager_data['players']) + (1 if manager_data['retained_player'] else 0)

def get_managers_with_zero_money(data):
    """Counts managers with $0 budget."""
    return sum(1 for m in data["managers"].values() if m["budget"] == 0)

async def send_status_embed(interaction: discord.Interaction, title_suffix=""):
    """Sends a formatted embed of the auction status."""
    data = load_data(DATA_FILE)
    embed = discord.Embed(
        title=f"FIFA Auction - Live Status {title_suffix}",
        color=discord.Color.brand_green()
    )
    
    if not data["managers"]:
        embed.description = "No managers in the auction. Use `/addmanager` to get started."
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    sorted_managers = sorted(data["managers"].values(), key=lambda m: m['budget'], reverse=True)
    player_cap = data.get("player_cap", DEFAULT_PLAYER_CAP)

    for m in sorted_managers:
        name = m["name"]
        budget = f"${m['budget']:,}"
        player_count = get_player_count(m)
        
        field_value = (
            f"**Budget:** {budget}\n"
            f"**Players:** {player_count} / {player_cap}"
        )
        embed.add_field(name=f"Manager: {name}", value=field_value, inline=True)
    
    # Send the response
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.followup.send(embed=embed)
    except discord.errors.InteractionResponded:
        await interaction.followup.send(embed=embed)

# --- NEW: Auto-Auction Functions ---

async def call_next_player(channel: discord.TextChannel):
    """Puts the next player from the queue on the block."""
    if bot.current_auction_task:
        bot.current_auction_task.cancel()
        bot.current_auction_task = None
        
    data = load_data(DATA_FILE)
    
    # Check if draft mode should start
    if await check_and_start_draft(channel):
        return # Draft mode has been initiated, stop auction queue

    if data["auction_queue_index"] >= len(data["auction_queue"]):
        await channel.send("🎉 **The auction queue is empty!** 🎉\nAll players have been auctioned. Moving to Draft Mode.")
        data["auction_state"] = "idle" # Set to idle before starting draft
        save_data(data, DATA_FILE)
        await check_and_start_draft(channel) # This will now start the draft
        return

    player_key = data["auction_queue"][data["auction_queue_index"]]
    data["auction_queue_index"] += 1
    
    player_db = load_data(PLAYER_DB_FILE)
    
    if player_key not in player_db:
        await channel.send(f"Player key `{player_key}` not in database. Skipping...")
        save_data(data, DATA_FILE)
        await call_next_player(channel) # Immediately call the next one
        return
        
    player = player_db[player_key]
    
    # Set auction state
    data["auction_state"] = "bidding"
    data["on_the_block"] = player
    data["current_bid"] = player["base_price"]
    data["current_bidder"] = None # No bidder yet
    save_data(data, DATA_FILE)
    
    # Announce the new player
    embed = discord.Embed(
        title=f"🔔 ON THE BLOCK: {player['name']} ({player['ovr']} OVR) 🔔",
        description=f"Team: **{player['team']}**\nBidding starts at: **${player['base_price']:,}**",
        color=discord.Color.blue()
    )
    await channel.send(embed=embed)

# --- Auction Countdown Logic ---

async def auction_countdown(channel: discord.TextChannel, player_name: str, final_bid: int, bidder_key: str):
    """The task that runs the live auction countdown."""
    data = load_data(DATA_FILE)
    if bidder_key not in data["managers"]:
        await channel.send(f"Error: Bidder {bidder_key} not found in manager list. Cancelling auction.")
        return
        
    manager_name = data["managers"][bidder_key]["name"]
    
    await channel.send(f"🔥 **New High Bid!** **{manager_name}** bids **${final_bid:,}** for **{player_name}**.\n"
                       f"Going once... going twice... ⏳ (`{BID_COUNTDOWN_SECONDS}` seconds)")
    
    try:
        await asyncio.sleep(BID_COUNTDOWN_SECONDS)
        
        # --- SOLD! ---
        data = load_data(DATA_FILE)
        
        if data["auction_state"] != "bidding" or not data["on_the_block"] or data["on_the_block"]["name"] != player_name:
            bot.current_auction_task = None
            return

        if bidder_key not in data["managers"]:
             await channel.send(f"Error: Winning bidder {bidder_key} no longer exists. Sale voided.")
             bot.current_auction_task = None
             return
             
        manager = data["managers"][bidder_key]
        player = data["on_the_block"] # Get OVR from here
        
        # Process Sale
        manager["budget"] -= final_bid
        manager["spent"] += final_bid
        manager["players"].append(f"{player_name} ({player['ovr']} OVR) - ${final_bid/1_000_000:.0f}M")
        
        player_db = load_data(PLAYER_DB_FILE)
        if player_name.lower() in player_db:
            player_db.pop(player_name.lower())
            save_data(player_db, PLAYER_DB_FILE)
        
        data["auction_state"] = "idle" # Set to idle temporarily
        data["on_the_block"] = None
        data["current_bid"] = 0
        data["current_bidder"] = None
        save_data(data, DATA_FILE)
        
        await channel.send(f"💸 **SOLD! {player_name}** joins **{manager_name}** for **${final_bid:,}**!\n"
                           f"💰 {manager_name} has ${manager['budget']:,} remaining.")
        
        if manager["budget"] == 0:
            await channel.send(f"🚨 **{manager_name}** has no money left! 🚨")
        
        bot.current_auction_task = None
        
        # Automatically call the next player
        await channel.send("Getting the next player...")
        await asyncio.sleep(2) # Brief pause
        await call_next_player(channel)

    except asyncio.CancelledError:
        await channel.send("...Bid interrupted! The auction continues! ⏳")
        return

async def steal_countdown(channel: discord.TextChannel, player_name: str, base_price: int, drafter_key: str):
    """The task that runs the draft steal countdown."""
    data = load_data(DATA_FILE)
    if drafter_key not in data["managers"]:
        await channel.send(f"Error: Drafter {drafter_key} not found. Cancelling draft pick.")
        return
        
    drafter_name = data["managers"][drafter_key]["name"]

    await channel.send(f"**{drafter_name}** has drafted **{player_name}** ({data['on_the_block']['ovr']} OVR).\n"
                       f"The steal price is **${base_price:,}**.\n"
                       f"Any manager with funds has **{STEAL_COUNTDOWN_SECONDS}** seconds to `/steal`! ⏳")
    
    try:
        await asyncio.sleep(STEAL_COUNTDOWN_SECONDS)
        
        # --- NOT STOLEN! ---
        data = load_data(DATA_FILE)
        if data["auction_state"] != "drafting" or not data["on_the_block"] or data["on_the_block"]["name"] != player_name:
            bot.current_steal_task = None
            return

        if drafter_key not in data["managers"]:
             await channel.send(f"Error: Drafter {drafter_key} no longer exists. Pick voided.")
             bot.current_steal_task = None
             return

        manager = data["managers"][drafter_key]
        player = data["on_the_block"] # Get OVR from here
        manager["players"].append(f"{player['name']} ({player['ovr']} OVR) - Draft")
        
        player_db = load_data(PLAYER_DB_FILE)
        if player_name.lower() in player_db:
            player_db.pop(player_key)
            save_data(player_db, PLAYER_DB_FILE)

        data["on_the_block"] = None
        data["draft_pick_index"] = (data["draft_pick_index"] + 1) % len(data["draft_order"])
        save_data(data, DATA_FILE)
        
        await channel.send(f"✅ **NOT STOLEN!** **{player_name}** officially joins **{drafter_name}**'s team!")
        bot.current_steal_task = None
        
        await advance_draft(channel)

    except asyncio.CancelledError:
        await channel.send("...Steal initiated! The auction is now live! 💰")
        return

# --- Bot Startup ---

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    load_data(DATA_FILE)
    load_data(PLAYER_DB_FILE)
    
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    
    print('------')

# --- NEW: Message-Based Bidding ---

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return # Ignore the bot's own messages
    
    # This ensures slash commands are still processed
    await bot.process_commands(message)

    data = load_data(DATA_FILE)
    
    # Only listen for bids if the auction is in "bidding" state
    if data["auction_state"] != "bidding":
        return

    # Try to parse the message as a number
    try:
        amount_in_millions = int(message.content)
    except ValueError:
        return # Not a number, ignore

    # --- It's a bid! ---
    bidder_key = message.author.display_name.lower()
    if bidder_key not in data["managers"]:
        await message.channel.send(f"🚫 {message.author.mention}, you are not a registered manager. Ask an admin to add you.", delete_after=10)
        return

    manager = data["managers"][bidder_key]
    player = data["on_the_block"]
    new_bid = amount_in_millions * 1_000_000
    
    # --- ALARM CHECKS ---
    if new_bid <= data["current_bid"]:
        await message.channel.send(f"🚫 **BID NOT VIABLE!** {message.author.mention}, your bid of **${new_bid:,}** must be *higher* than the current bid of **${data['current_bid']:,}**.", delete_after=10)
        return
        
    if new_bid > manager["budget"]:
        await message.channel.send(f"🚫 **MONEY OVER!** {message.author.mention}, you cannot afford this bid.\n"
                                   f"Your Budget: **${manager['budget']:,}** | Your Bid: **${new_bid:,}**", delete_after=10)
        return

    player_cap = data.get("player_cap", DEFAULT_PLAYER_CAP)
    player_count = get_player_count(manager)
    if player_count >= player_cap:
        await message.channel.send(f"🚫 **TEAM CAP FULL!** {message.author.mention}, you already have {player_cap} players.", delete_after=10)
        return
    
    if data["current_bidder"] == bidder_key:
        await message.channel.send(f"❌ {message.author.mention}, you are already the highest bidder!", delete_after=10)
        return
        
    # --- BID ACCEPTED ---
    
    # Cancel the previous countdown
    if bot.current_auction_task:
        bot.current_auction_task.cancel()
    
    # Update the auction state
    data["current_bid"] = new_bid
    data["current_bidder"] = bidder_key
    save_data(data, DATA_FILE)
    
    # Start the new countdown
    bot.current_auction_task = bot.loop.create_task(
        auction_countdown(message.channel, player["name"], new_bid, bidder_key)
    )

# --- Admin Slash Commands ---

@tree.command(name="reset", description="Resets the entire auction. (Admin Only)")
@commands.has_permissions(administrator=True)
async def reset_command(interaction: discord.Interaction):
    data = get_default_data()
    save_data(data, DATA_FILE)
    
    if os.path.exists(PLAYER_DB_FILE + ".bak"):
        shutil.copy(PLAYER_DB_FILE + ".bak", PLAYER_DB_FILE)
        await interaction.response.send_message("🚨 **AUCTION RESET!** 🚨\nAll managers, players, and budgets cleared. Player database reset from backup.")
    else:
        save_data({}, PLAYER_DB_FILE)
        await interaction.response.send_message("🚨 **AUCTION RESET!** 🚨\nAll managers, players, and budgets cleared. Player database is now empty.")

@tree.command(name="undo", description="Undoes the last transaction. (Admin Only)")
@commands.has_permissions(administrator=True)
async def undo_command(interaction: discord.Interaction):
    if os.path.exists(BACKUP_FILE):
        shutil.copy(BACKUP_FILE, DATA_FILE)
        await interaction.response.send_message("⏪ **Last transaction undone!** The auction has been rolled back.")
        await send_status_embed(interaction)
    else:
        await interaction.response.send_message("❌ No backup file found to undo.", ephemeral=True)

@tree.command(name="addmanager", description="Adds a new manager to the auction.")
@discord.app_commands.describe(name="The manager's name (use quotes for spaces)", budget_in_millions="The starting budget (e.g., 1000)")
@commands.has_permissions(administrator=True)
async def addmanager_command(interaction: discord.Interaction, name: str, budget_in_millions: int):
    data = load_data(DATA_FILE)
    key = name.lower()
    
    if key in data["managers"]:
        await interaction.response.send_message(f"❌ **Error:** A manager named **{name}** already exists.", ephemeral=True)
        return

    budget = budget_in_millions * 1_000_000
    data["managers"][key] = {
        "name": name,
        "budget": budget,
        "spent": 0,
        "players": [],
        "retained_player": None
    }
    save_data(data, DATA_FILE)
    await interaction.response.send_message(f"✅ **Manager Added!** Welcome, **{name}**, with a budget of **${budget:,}**.")
    await send_status_embed(interaction)

@tree.command(name="removemanager", description="Removes a manager from the auction.")
@discord.app_commands.describe(name="The name of the manager to remove")
@commands.has_permissions(administrator=True)
async def removemanager_command(interaction: discord.Interaction, name: str):
    data = load_data(DATA_FILE)
    key = name.lower()
    
    if key not in data["managers"]:
        await interaction.response.send_message(f"❌ **Error:** Manager '{name}' not found.", ephemeral=True)
        return
        
    removed_manager = data["managers"].pop(key)
    save_data(data, DATA_FILE)
    await interaction.response.send_message(f"🗑️ **Manager Removed!** **{removed_manager['name']}** has left the auction.")
    await send_status_embed(interaction)

@tree.command(name="setcap", description="Sets the player cap for all teams.")
@discord.app_commands.describe(cap="The max number of players per team (e.g., 18)")
@commands.has_permissions(administrator=True)
async def setcap_command(interaction: discord.Interaction, cap: int):
    if cap <= 0:
        await interaction.response.send_message("❌ Cap must be a positive number.", ephemeral=True)
        return
    data = load_data(DATA_FILE)
    data["player_cap"] = cap
    save_data(data, DATA_FILE)
    await interaction.response.send_message(f"🧢 **Team cap set to {cap} players!**")

@tree.command(name="pause", description="Pauses the current auction countdown.")
@commands.has_permissions(administrator=True)
async def pause_command(interaction: discord.Interaction):
    data = load_data(DATA_FILE)
    if data["auction_state"] not in ["bidding", "drafting"]:
        await interaction.response.send_message("❌ No auction or draft is currently active.", ephemeral=True)
        return

    # Cancel the running task
    if data["auction_state"] == "bidding" and bot.current_auction_task:
        bot.current_auction_task.cancel()
        bot.current_auction_task = None
    elif data["auction_state"] == "drafting" and bot.current_steal_task:
        bot.current_steal_task.cancel()
        bot.current_steal_task = None
        
    data["auction_state"] = "paused"
    save_data(data, DATA_FILE)
    await interaction.response.send_message("⏸️ **Auction Paused!** The countdown has been stopped.\n")

@tree.command(name="resume", description="Resumes a paused auction.")
@commands.has_permissions(administrator=True)
async def resume_command(interaction: discord.Interaction):
    data = load_data(DATA_FILE)
    if data["auction_state"] != "paused":
        await interaction.response.send_message("❌ No auction is currently paused.", ephemeral=True)
        return
    
    await interaction.response.send_message("▶️ **Auction Resumed!**")
    
    # Check if we are resuming a bid or a steal
    if data["on_the_block"] and data["current_bidder"]:
        # Resuming a bid
        data["auction_state"] = "bidding"
        save_data(data, DATA_FILE)
        bot.current_auction_task = bot.loop.create_task(
            auction_countdown(interaction.channel, data["on_the_block"]["name"], data["current_bid"], data["current_bidder"])
        )
    elif data["on_the_block"] and data["draft_order"]: 
         # Resuming a draft steal
        data["auction_state"] = "drafting"
        save_data(data, DATA_FILE)
        drafter_key_index = data["draft_pick_index"]
        if drafter_key_index == 0:
             drafter_key = data["draft_order"][0]
        else:
             drafter_key = data["draft_order"][drafter_key_index - 1] 
             
        bot.current_steal_task = bot.loop.create_task(
            steal_countdown(interaction.channel, data["on_the_block"]["name"], data["on_the_block"]["base_price"], drafter_key)
        )
    else:
        # Just unpausing, go to idle
        data["auction_state"] = "idle"
        save_data(data, DATA_FILE)


@tree.command(name="unsold", description="Marks the player on the block as unsold and calls the next player.")
@commands.has_permissions(administrator=True)
async def unsold_command(interaction: discord.Interaction):
    data = load_data(DATA_FILE)
    if data["auction_state"] not in ["bidding", "paused"]:
        await interaction.response.send_message("❌ No auction is currently active.", ephemeral=True)
        return
        
    if bot.current_auction_task:
        bot.current_auction_task.cancel()
        bot.current_auction_task = None

    player_name = data["on_the_block"]["name"]
    data["auction_state"] = "idle" # Set to idle temporarily
    data["on_the_block"] = None
    data["current_bid"] = 0
    data["current_bidder"] = None
    save_data(data, DATA_FILE)

    await interaction.response.send_message(f"🚫 **{player_name}** is **UNSOLD** and returns to the player pool.")
    
    # Automatically call the next player
    await interaction.channel.send("Getting the next player...")
    await asyncio.sleep(2) # Brief pause
    await call_next_player(interaction.channel)

# --- Player Database Commands ---

@tree.command(name="editplayer", description="Add or edit a player in the player database.")
@discord.app_commands.describe(name="Player's full name (use quotes)", team="Player's real-life team", ovr="Player OVR (e.g., 88)", base_price="Base price in millions (e.g., 10)")
@commands.has_permissions(administrator=True)
async def editplayer_command(interaction: discord.Interaction, name: str, team: str, ovr: int, base_price: int):
    if not os.path.exists(PLAYER_DB_FILE + ".bak"):
        shutil.copy(PLAYER_DB_FILE, PLAYER_DB_FILE + ".bak")
        
    player_db = load_data(PLAYER_DB_FILE)
    key = name.lower()
    player_db[key] = {
        "name": name,
        "team": team,
        "ovr": ovr,
        "base_price": base_price * 1_000_000
    }
    save_data(player_db, PLAYER_DB_FILE)
    await interaction.response.send_message(f"✅ **Player Database Updated!**\n"
                                          f"**{name}** ({ovr} OVR, Team: {team}, Base Price: ${base_price:,}M)")

@tree.command(name="listplayers", description="Lists all available players from the database.")
async def listplayers_command(interaction: discord.Interaction):
    player_db = load_data(PLAYER_DB_FILE)
    if not player_db:
        await interaction.response.send_message("Player database is empty. Use `/editplayer` to add players.", ephemeral=True)
        return

    embed = discord.Embed(title="Available Players", color=discord.Color.gold())
    
    player_list = []
    # Sort by OVR, then by name
    sorted_players = sorted(player_db.values(), key=lambda p: (-p['ovr'], p['name']))
    
    for player in sorted_players:
        player_list.append(f"• **{player['name']}** ({player['ovr']} OVR) - Team: {player['team']}, Base: ${player['base_price']:,}")

    description = "\n".join(player_list)
    if len(description) > 4000:
        description = description[:4000] + "\n...and many more."
        
    embed.description = description
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="playerinfo", description="Gets the info for one player.")
@discord.app_commands.describe(name="Player's name")
async def playerinfo_command(interaction: discord.Interaction, name: str):
    player_db = load_data(PLAYER_DB_FILE)
    key = name.lower()
    
    if key not in player_db:
        await interaction.response.send_message(f"❌ Player **{name}** not found in the database.", ephemeral=True)
        return
        
    player = player_db[key]
    embed = discord.Embed(title=f"{player['name']} ({player['ovr']} OVR)", color=discord.Color.blue())
    embed.add_field(name="Real Team", value=player['team'], inline=True)
    embed.add_field(name="Base Price", value=f"${player['base_price']:,}", inline=True)
    await interaction.response.send_message(embed=embed)

# --- Live Auction Commands ---

@tree.command(name="start", description="STARTS the tiered, automatic auction!")
@commands.has_permissions(administrator=True)
async def start_command(interaction: discord.Interaction):
    data = load_data(DATA_FILE)
    player_db = load_data(PLAYER_DB_FILE)
    
    if data["auction_state"] != "idle":
        await interaction.response.send_message("❌ Cannot start! An auction or draft is already in progress.", ephemeral=True)
        return
    
    if not data["managers"]:
        await interaction.response.send_message("❌ Cannot start! Add managers with `/addmanager` first.", ephemeral=True)
        return

    if not player_db:
        await interaction.response.send_message("❌ Cannot start! The player database is empty.", ephemeral=True)
        return

    await interaction.response.send_message("🚀 **Auction Starting!**\nBuilding player queue...")

    # --- Build the Queue ---
    retained_players = {m['retained_player'].lower() for m in data["managers"].values() if m['retained_player']}
    
    tier1 = [] # 86+
    tier2 = [] # 83-85
    tier3 = [] # <=82
    
    for key, player in player_db.items():
        if key in retained_players:
            continue # Skip retained player
        
        ovr = player.get('ovr', 0)
        if ovr >= 86:
            tier1.append(key)
        elif ovr >= 83:
            tier2.append(key)
        else:
            tier3.append(key)
            
    # Shuffle each tier
    random.shuffle(tier1)
    random.shuffle(tier2)
    random.shuffle(tier3)
    
    # Create master queue
    data["auction_queue"] = tier1 + tier2 + tier3
    data["auction_queue_index"] = 0
    
    if not data["auction_queue"]:
        await interaction.followup.send("❌ Cannot start! No players are available after filtering retained players.")
        return
        
    await interaction.followup.send(f"✅ **Auction Queue is ready!**\n"
                                     f"• **Tier 1 (86+ OVR):** {len(tier1)} players\n"
                                     f"• **Tier 2 (83-85 OVR):** {len(tier2)} players\n"
                                     f"• **Tier 3 (<=82 OVR):** {len(tier3)} players\n"
                                     f"Total: **{len(data['auction_queue'])}** players on the block.\n\n"
                                     f"Calling the first player...")
    
    save_data(data, DATA_FILE)
    await asyncio.sleep(3) # Dramatic pause
    await call_next_player(interaction.channel)


# --- Draft Mode Commands ---

async def check_and_start_draft(channel: discord.TextChannel):
    """Checks if draft mode should be triggered and starts it. Returns True if draft started."""
    data = load_data(DATA_FILE)
    if data["auction_state"] == "drafting":
        return True # Already in draft mode
        
    if data["auction_state"] not in ["idle", "bidding"]:
        return False # Paused or other state
        
    managers_at_zero = get_managers_with_zero_money(data)
    
    if managers_at_zero >= 3:
        if bot.current_auction_task: # Cancel any pending sale
            bot.current_auction_task.cancel()
            bot.current_auction_task = None
            
        await channel.send(f"🚨 **{managers_at_zero} MANAGERS** have no money! **DRAFT MODE INITIATED!** 🚨")
        
        zero_money_managers = [k for k, m in data["managers"].items() if m["budget"] == 0]
        money_managers = [k for k, m in data["managers"].items() if m["budget"] > 0]
        
        money_managers.sort(key=lambda k: data["managers"][k]["budget"])
        
        draft_order = zero_money_managers + money_managers
        
        data["auction_state"] = "drafting"
        data["draft_order"] = draft_order
        data["draft_pick_index"] = 0
        save_data(data, DATA_FILE)
        
        await advance_draft(channel)
        return True
    return False

async def advance_draft(channel: discord.TextChannel):
    """Announces the next pick in the draft."""
    data = load_data(DATA_FILE)
    if data["auction_state"] != "drafting":
        return
        
    idx = data["draft_pick_index"]
    
    all_full = all(get_player_count(m) >= data["player_cap"] for m in data["managers"].values())
    if all_full:
        await channel.send("🎉 **All teams are full! The draft is complete!** 🎉")
        data["auction_state"] = "idle"
        save_data(data, DATA_FILE)
        return
        
    drafter_key = data["draft_order"][idx]
    drafter_name = data["managers"][drafter_key]["name"]
    
    if get_player_count(data["managers"][drafter_key]) >= data["player_cap"]:
        await channel.send(f"Skipping **{drafter_name}** (team full).")
        data["draft_pick_index"] = (idx + 1) % len(data["draft_order"])
        save_data(data, DATA_FILE)
        await advance_draft(channel) 
        return

    await channel.send(f"It is **Pick #{idx + 1}**.\n"
                       f"On the clock: **{drafter_name}**! Use `/draft [Player Name]`")

@tree.command(name="startdraft", description="Manually start the draft. (Admin Only)")
@commands.has_permissions(administrator=True)
async def startdraft_command(interaction: discord.Interaction):
    data = load_data(DATA_FILE)
    if data["auction_state"] not in ["idle", "paused"]:
        await interaction.response.send_message("❌ Cannot start draft! Auction or another draft is in progress.", ephemeral=True)
        return
        
    await interaction.response.send_message("Manually initiating draft...")
    await check_and_start_draft(interaction.channel)


@tree.command(name="draft", description="Draft a player when it's your turn.")
@discord.app_commands.describe(name="The name of the player you are drafting")
async def draft_command(interaction: discord.Interaction, name: str):
    data = load_data(DATA_FILE)
    
    if data["auction_state"] != "drafting":
        await interaction.response.send_message("❌ It is not draft mode.", ephemeral=True)
        return
        
    drafter_key = data["draft_order"][data["draft_pick_index"]]
    drafter_name = data["managers"][drafter_key]["name"]
    
    user_key = interaction.user.display_name.lower()
    
    if user_key != drafter_key:
        await interaction.response.send_message(f"❌ It's not your turn! It is **{drafter_name}**'s pick.", ephemeral=True)
        return
        
    player_db = load_data(PLAYER_DB_FILE)
    player_key = name.lower()
    
    if player_key not in player_db:
        await interaction.response.send_message(f"❌ Player **{name}** not in database. Use `/editplayer` or pick another.", ephemeral=True)
        return
        
    player = player_db[player_key]
    base_price = player["base_price"]
    
    can_be_stolen = any(m["budget"] >= base_price for k, m in data["managers"].items() if k != drafter_key)
    
    await interaction.response.send_message(f"**{drafter_name}** is on the clock and selects **{player['name']}**...", ephemeral=True)

    if not can_be_stolen:
        await interaction.channel.send(f"**{drafter_name}** selects **{player['name']}** ({player['ovr']} OVR).\n"
                                       "No managers have enough money to steal. The pick is final!")
        
        manager = data["managers"][drafter_key]
        manager["players"].append(f"{player['name']} ({player['ovr']} OVR) - Draft")
        player_db.pop(player_key)
        save_data(player_db, PLAYER_DB_FILE)
        
        data["draft_pick_index"] = (data["draft_pick_index"] + 1) % len(data["draft_order"])
        save_data(data, DATA_FILE)
        
        await advance_draft(interaction.channel)
        return

    # --- Start the Steal Countdown ---
    data["on_the_block"] = player
    save_data(data, DATA_FILE)
    
    bot.current_steal_task = bot.loop.create_task(
        steal_countdown(interaction.channel, player["name"], base_price, drafter_key)
    )

@tree.command(name="steal", description="Steal the currently drafted player and start an auction!")
async def steal_command(interaction: discord.Interaction):
    data = load_data(DATA_FILE)
    
    if data["auction_state"] != "drafting" or not data["on_the_block"]:
        await interaction.response.send_message("❌ No player is currently being drafted or stolen.", ephemeral=True)
        return
        
    if not bot.current_steal_task or bot.current_steal_task.done():
        await interaction.response.send_message("❌ The steal window has closed!", ephemeral=True)
        return

    stealer_key = interaction.user.display_name.lower()
    
    if stealer_key not in data["managers"]:
        await interaction.response.send_message("❌ You are not a registered manager.", ephemeral=True)
        return
        
    manager = data["managers"][stealer_key]
    player = data["on_the_block"]
    base_price = player["base_price"]
    
    # --- ALARM CHECKS ---
    if manager["budget"] < base_price:
        await interaction.response.send_message(f"🚫 **MONEY OVER!** You cannot afford the **${base_price:,}** steal price.", ephemeral=True)
        return
        
    player_cap = data.get("player_cap", DEFAULT_PLAYER_CAP)
    player_count = get_player_count(manager)
    if player_count >= player_cap:
        await interaction.response.send_message(f"🚫 **TEAM CAP FULL!** You already have {player_cap} players.", ephemeral=True)
        return

    # --- STEAL ACCEPTED ---
    await interaction.response.send_message(f"**{manager['name']}** is stealing!", ephemeral=True)

    bot.current_steal_task.cancel()
    bot.current_steal_task = None
    
    data["auction_state"] = "bidding"
    data["current_bid"] = base_price
    data["current_bidder"] = stealer_key
    save_data(data, DATA_FILE)
    
    bot.current_auction_task = bot.loop.create_task(
        auction_countdown(interaction.channel, player["name"], base_price, stealer_key)
    )

# --- Public Slash Commands ---

@tree.command(name="status", description="Displays the current auction board.")
async def status_command(interaction: discord.Interaction):
    await send_status_embed(interaction, title_suffix=f"({load_data(DATA_FILE)['auction_state']})")

@tree.command(name="team", description="Shows the full squad for one manager.")
@discord.app_commands.describe(name="The name of the manager")
async def team_command(interaction: discord.Interaction, name: str):
    data = load_data(DATA_FILE)
    key = name.lower()
    if key not in data["managers"]:
        await interaction.response.send_message(f"❌ **Error:** Manager '{name}' not found.", ephemeral=True)
        return

    manager = data["managers"][key]
    player_count = get_player_count(manager)
    player_cap = data.get("player_cap", DEFAULT_PLAYER_CAP)

    embed = discord.Embed(
        title=f"Squad Report: {manager['name']}",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Retained Player", value=f"**{manager['retained_player']}**" if manager['retained_player'] else "None", inline=True)
    embed.add_field(name="Remaining Budget", value=f"**${manager['budget']:,}**", inline=True)
    embed.add_field(name="Total Spent", value=f"${manager['spent']:,}", inline=True)
    
    player_list = []
    if manager["retained_player"]:
        player_list.append(f"• **{manager['retained_player']}** (Retained)")
    
    player_list.extend([f"• {player}" for player in manager['players']])
    
    if not player_list:
        player_list_str = "No players yet."
    else:
        player_list_str = "\n".join(player_list)
        if len(player_list_str) > 1024:
             player_list_str = player_list_str[:1020] + "\n..."

    embed.add_field(name=f"Full Squad ({player_count} / {player_cap} players)", value=player_list_str, inline=False)
    
    await interaction.response.send_message(embed=embed)

@tree.command(name="retain", description="Retains one player for your team (Admin).")
@discord.app_commands.describe(player_name="The name of the player to retain", manager_name="The manager who is retaining")
@commands.has_permissions(administrator=True)
async def retain_command(interaction: discord.Interaction, player_name: str, manager_name: str):
    """Assigns a retained player to a manager."""
    data = load_data(DATA_FILE)
    key = manager_name.lower()
    if key not in data["managers"]:
        await interaction.response.send_message(f"❌ **Error:** Manager '{manager_name}' not found.", ephemeral=True)
        return
    
    manager = data["managers"][key]
    if manager["retained_player"]:
        await interaction.response.send_message(f"⚠️ **{manager['name']}** has already retained **{manager['retained_player']}**! Use `/undo` to fix.", ephemeral=True)
        return
        
    player_db = load_data(PLAYER_DB_FILE)
    player_key = player_name.lower()
    
    if player_key not in player_db:
        await interaction.response.send_message(f"❌ Player **{player_name}** not in database. Cannot retain.", ephemeral=True)
        return
        
    player_data = player_db.pop(player_key) # Remove from DB
    save_data(player_db, PLAYER_DB_FILE)
    
    manager["retained_player"] = f"{player_data['name']} ({player_data['ovr']} OVR)"
    save_data(data, DATA_FILE)
    
    await interaction.response.send_message(f"✅ **{manager['name']}** has retained **{player_data['name']}**!")
    await send_status_embed(interaction)

# --- Error Handling ---
async def on_tree_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.MissingPermissions):
        await interaction.response.send_message("🚫 You do not have permission to use this command.", ephemeral=True)
    elif isinstance(error, discord.app_commands.CommandInvokeError):
        print(f"Command {interaction.data['name']} failed with error: {error.original}")
        if not interaction.response.is_done():
            await interaction.response.send_message("An unexpected error occurred. Please check the console.", ephemeral=True)
        else:
            await interaction.followup.send("An unexpected error occurred. Please check the console.", ephemeral=True)
    elif isinstance(error, discord.app_commands.CommandNotFound):
        pass
    else:
        print(f"Unhandled app command error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("An unknown error occurred.", ephemeral=True)
        
bot.tree.on_error = on_tree_error

# --- Run Bot ---
if not TOKEN:
    print("FATAL ERROR: DISCORD_TOKEN not found in .env file.")
else:
    bot.run(TOKEN)
