import discord
from discord.ext import commands
import sqlite3
from datetime import datetime
import os

# Initialize bot
intents = discord.Intents.all()  # Allow full bot functionality
bot = commands.Bot(command_prefix="!", intents=intents)

# SQLite database setup
def get_db_connection():
    """Returns a connection to the database."""
    return sqlite3.connect("sobriety_tracker.db", check_same_thread=False)

db = get_db_connection()
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS sobriety_data (
    user_id INTEGER PRIMARY KEY,
    sobriety_date TEXT,
    substance TEXT,
    is_private INTEGER DEFAULT 0
)
""")
db.commit()

# Helper function to calculate days sober
def calculate_days_sober(date_str):
    try:
        sober_date = datetime.strptime(date_str, "%m-%d-%y")
        return (datetime.now() - sober_date).days
    except ValueError:
        return None

# Custom decorator to check for a specific role or Administrator permission
def has_specific_role_or_admin(required_role: str):
    async def predicate(interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            return True
        role_names = [role.name for role in interaction.user.roles]
        return required_role in role_names
    return commands.check(predicate)

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()  # Force sync all slash commands
        print(f"✅ {bot.user} is online and commands are synced!")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

# User commands
@bot.tree.command(name="set", description="Set your sobriety date and substance.")
async def set(interaction: discord.Interaction, date: str, substance: str):
    try:
        sober_date = datetime.strptime(date, "%m-%d-%y").strftime("%m-%d-%y")
        with get_db_connection() as db:
            cursor = db.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO sobriety_data (user_id, sobriety_date, substance)
                VALUES (?, ?, ?)
            """, (interaction.user.id, sober_date, substance))
            db.commit()

        embed = discord.Embed(
            title="🎉 Sobriety Date Set! 🎉",
            description=f"**{interaction.user.mention}, your sobriety journey starts here!**\n\n"
                        f"📅 **Date:** `{sober_date}`\n"
                        f"💊 **Substance:** `{substance}`",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    except ValueError:
        embed = discord.Embed(
            title="❌ Invalid Date Format ❌",
            description="**Use the format `MM-DD-YY` (e.g., `01-01-25`).**\n\n"
                        "**Example Usage:**\n"
                        "`/set 01-01-25 Alcohol`\n"
                        "`/set 01-01-25 All Substances`",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="view", description="View your or another user's sobriety details.")
async def view(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    with get_db_connection() as db:
        cursor = db.cursor()
        cursor.execute("SELECT sobriety_date, substance, is_private FROM sobriety_data WHERE user_id = ?", (member.id,))
        data = cursor.fetchone()

    if data:
        if data[2] and member != interaction.user:
            await interaction.response.send_message(f"🔒 {member.mention} has chosen to keep their sobriety details private.")
        else:
            days_sober = calculate_days_sober(data[0])
            if days_sober is not None:
                embed = discord.Embed(
                    title="🌟 Sobriety Details 🌟",
                    description=f"Here are the details for {member.mention}:",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Days Sober:", value=f"`{days_sober}` days", inline=True)
                embed.add_field(name="Substance:", value=f"`{data[1]}`", inline=True)
                embed.add_field(name="Since:", value=f"`{data[0]}`", inline=False)
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(f"⚠️ {member.mention}, your sobriety date is invalid. Please reset it.")
    else:
        await interaction.response.send_message(f"❌ {member.mention} has not set their sobriety details.")

@bot.tree.command(name="leaderboard", description="View the leaderboard of sobriety streaks.")
async def leaderboard(interaction: discord.Interaction):
    with get_db_connection() as db:
        cursor = db.cursor()
        cursor.execute("SELECT user_id, sobriety_date, substance FROM sobriety_data")
        records = cursor.fetchall()

    leaderboard = sorted(
        records,
        key=lambda x: calculate_days_sober(x[1]) if calculate_days_sober(x[1]) is not None else 0,
        reverse=True
    )

    if leaderboard:
        embed = discord.Embed(
            title="🏆 Sobriety Leaderboard 🏆",
            description="Top sobriety streaks in the server:",
            color=discord.Color.gold()
        )
        for i, record in enumerate(leaderboard[:10], 1):
            user = await bot.fetch_user(record[0])
            days_sober = calculate_days_sober(record[1])
            embed.add_field(
                name=f"{i}. {user.name}",
                value=f"`{days_sober}` days sober from `{record[2]}` (since `{record[1]}`)",
                inline=False
            )
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("🚫 No sobriety data available yet. Be the first to set yours!")

@bot.tree.command(name="admin_remove", description="Remove a user's sobriety data.")
@has_specific_role_or_admin("Moderator")
async def admin_remove(interaction: discord.Interaction, member: discord.Member):
    with get_db_connection() as db:
        cursor = db.cursor()
        cursor.execute("DELETE FROM sobriety_data WHERE user_id = ?", (member.id,))
        db.commit()

    await interaction.response.send_message(f"🗑️ Sobriety data for {member.mention} has been removed.")

# Run the bot
bot.run(os.getenv("DISCORD_TOKEN"))
