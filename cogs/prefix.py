import nextcord
from nextcord.ext import commands
import sqlite3
import os
import asyncio
from typing import List, Dict, Set
import json

class DynamicPrefix(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Cache structure: {guild_id: set(prefixes)}
        self.prefix_cache: Dict[int, Set[str]] = {}
        self.default_prefix = "!"
        self.setup_database()
        self.load_prefixes()
        
        # Replace bot's command_prefix with our dynamic method
        self.bot.command_prefix = self.get_prefix
        
    def setup_database(self):
        """Set up the SQLite database and required tables"""
        # Create db directory if it doesn't exist
        if not os.path.exists('db'):
            os.makedirs('db')
            
        # Connect to database and create table if it doesn't exist
        with sqlite3.connect('db/prefixes.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS guild_prefixes (
                guild_id INTEGER,
                prefix TEXT,
                PRIMARY KEY (guild_id, prefix)
            )
            ''')
            conn.commit()
    
    def load_prefixes(self):
        """Load all prefixes from the database into the cache"""
        with sqlite3.connect('db/prefixes.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT guild_id, prefix FROM guild_prefixes')
            
            for guild_id, prefix in cursor.fetchall():
                if guild_id not in self.prefix_cache:
                    self.prefix_cache[guild_id] = set()
                self.prefix_cache[guild_id].add(prefix)
    
    async def get_prefix(self, bot, message):
        """Dynamic prefix getter for the bot"""
        # In DMs, only use default prefix
        if message.guild is None:
            return self.default_prefix
            
        guild_id = message.guild.id
        
        # Start with default prefix
        prefixes = [self.default_prefix]
        
        # Add any custom prefixes for this guild
        if guild_id in self.prefix_cache and self.prefix_cache[guild_id]:
            prefixes.extend(list(self.prefix_cache[guild_id]))
            
        return prefixes
    
    def add_prefix_to_db(self, guild_id: int, prefix: str) -> bool:
        """Add a prefix to the database if it doesn't exist already"""
        try:
            with sqlite3.connect('db/prefixes.db') as conn:
                cursor = conn.cursor()
                
                # Check if prefix already exists
                cursor.execute('SELECT 1 FROM guild_prefixes WHERE guild_id = ? AND prefix = ?', 
                             (guild_id, prefix))
                if cursor.fetchone():
                    return False  # Prefix already exists
                
                # Add the new prefix
                cursor.execute('INSERT INTO guild_prefixes (guild_id, prefix) VALUES (?, ?)',
                              (guild_id, prefix))
                conn.commit()
                
                # Update cache
                if guild_id not in self.prefix_cache:
                    self.prefix_cache[guild_id] = set()
                self.prefix_cache[guild_id].add(prefix)
                return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
    
    def remove_prefix_from_db(self, guild_id: int, prefix: str) -> bool:
        """Remove a specific prefix from the database"""
        try:
            with sqlite3.connect('db/prefixes.db') as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM guild_prefixes WHERE guild_id = ? AND prefix = ?', 
                             (guild_id, prefix))
                conn.commit()
                
                # If we actually deleted something
                if cursor.rowcount > 0:
                    # Update cache
                    if guild_id in self.prefix_cache and prefix in self.prefix_cache[guild_id]:
                        self.prefix_cache[guild_id].remove(prefix)
                    return True
                return False
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
    
    def get_all_prefixes(self, guild_id: int) -> List[str]:
        """Get all prefixes for a specific guild"""
        if guild_id in self.prefix_cache:
            return [self.default_prefix] + list(self.prefix_cache[guild_id])
        return [self.default_prefix]
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def addprefix(self, ctx, prefix: str):
        """Add a custom prefix for the server (Admin only)"""
        if not prefix:
            await ctx.send("Prefix cannot be empty.")
            return
            
        if len(prefix) > 10:
            await ctx.send("Prefix is too long. Maximum length is 10 characters.")
            return
        
        # Check if we're at the limit (prevent prefix spam)
        prefixes = self.get_all_prefixes(ctx.guild.id)
        if len(prefixes) >= 10:  # Allow up to 10 prefixes including default
            await ctx.send("Maximum number of prefixes reached (9). Please remove some before adding more.")
            return
            
        # Try to add the prefix
        success = self.add_prefix_to_db(ctx.guild.id, prefix)
        
        if success:
            await ctx.send(f"Prefix `{prefix}` added successfully.")
        else:
            await ctx.send(f"Prefix `{prefix}` already exists.")
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def deleteprefix(self, ctx, prefix: str):
        """Delete a specific custom prefix for the server (Admin only)"""
        if prefix == self.default_prefix:
            await ctx.send(f"Cannot remove the default prefix `{self.default_prefix}`.")
            return
            
        success = self.remove_prefix_from_db(ctx.guild.id, prefix)
        
        if success:
            await ctx.send(f"Prefix `{prefix}` removed successfully.")
        else:
            await ctx.send(f"Prefix `{prefix}` not found.")
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def clearprefixes(self, ctx):
        """Remove all custom prefixes for this server (Admin only)"""
        try:
            with sqlite3.connect('db/prefixes.db') as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM guild_prefixes WHERE guild_id = ?', (ctx.guild.id,))
                conn.commit()
                
                # Clear the cache for this guild
                if ctx.guild.id in self.prefix_cache:
                    self.prefix_cache[ctx.guild.id] = set()
                
                await ctx.send(f"All custom prefixes removed. Using default prefix `{self.default_prefix}`.")
        except sqlite3.Error as e:
            await ctx.send(f"Error clearing prefixes: {e}")
    
    @commands.command(aliases=["prefixes"])
    async def showprefixes(self, ctx):
        """Show all current prefixes for this server"""
        prefixes = self.get_all_prefixes(ctx.guild.id)
        
        if len(prefixes) == 1:
            await ctx.send(f"Using default prefix: `{self.default_prefix}`")
        else:
            # Format the prefixes nicely
            prefix_list = "\n".join([f"• `{p}`" + (" (default)" if p == self.default_prefix else "") for p in prefixes])
            embed = nextcord.Embed(
                title=f"Prefixes for {ctx.guild.name}",
                description=f"The following prefixes are active:\n{prefix_list}",
                color=0x3498db
            )
            await ctx.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        """Clean up prefixes when bot leaves a guild"""
        try:
            with sqlite3.connect('db/prefixes.db') as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM guild_prefixes WHERE guild_id = ?', (guild.id,))
                conn.commit()
                
            # Remove from cache
            if guild.id in self.prefix_cache:
                del self.prefix_cache[guild.id]
        except sqlite3.Error as e:
            print(f"Error cleaning up prefixes for guild {guild.id}: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Process commands with the dynamic prefix"""
        # Already handled by the bot's command processing
        # This is here for any additional prefix-related processing if needed
        pass

def setup(bot):
    bot.add_cog(DynamicPrefix(bot))
