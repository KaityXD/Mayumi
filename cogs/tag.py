import nextcord
from nextcord.ext import commands
import json
import os
import difflib
import asyncio
from typing import Dict, List, Optional

# Tag data file
TAG_FILE = "tags.json"

# Initialize tags file if it doesn't exist
if not os.path.exists(TAG_FILE):
    with open(TAG_FILE, "w") as f:
        json.dump({}, f)


def load_tags() -> Dict[str, str]:
    """Load tags from the JSON file."""
    try:
        with open(TAG_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_tags(tags: Dict[str, str]) -> None:
    """Save tags to the JSON file."""
    with open(TAG_FILE, "w") as f:
        json.dump(tags, f, indent=4)


class TagManagementView(nextcord.ui.View):
    """View for managing tags."""

    def __init__(self, cog: "TagSystem", tags: Dict[str, str]):
        super().__init__(timeout=300)
        self.cog = cog
        self.tags = tags

    @nextcord.ui.button(label="Create Tag", style=nextcord.ButtonStyle.green)
    async def create_tag(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        # Create modal for tag creation
        modal = TagCreateModal(self.cog)
        await interaction.response.send_modal(modal)

    @nextcord.ui.button(label="Edit Tag", style=nextcord.ButtonStyle.blurple)
    async def edit_tag(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        # Create modal for tag editing
        modal = TagSelectModal(self.cog, mode="edit")
        await interaction.response.send_modal(modal)

    @nextcord.ui.button(label="Delete Tag", style=nextcord.ButtonStyle.red)
    async def delete_tag(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        # Create modal for tag deletion
        modal = TagSelectModal(self.cog, mode="delete")
        await interaction.response.send_modal(modal)

    @nextcord.ui.button(label="List Tags", style=nextcord.ButtonStyle.gray)
    async def list_tags(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.cog.display_tags_paginated(interaction)


class TagCreateModal(nextcord.ui.Modal):
    """Modal for creating a new tag."""

    def __init__(self, cog: "TagSystem"):
        super().__init__(title="Create Tag")
        self.cog = cog

        self.tag_name = nextcord.ui.TextInput(
            label="Tag Name",
            placeholder="Enter the tag name",
            required=True,
            max_length=100
        )
        self.add_item(self.tag_name)

        self.tag_content = nextcord.ui.TextInput(
            label="Tag Content",
            placeholder="Enter the tag content",
            required=True,
            style=nextcord.TextInputStyle.paragraph,
            max_length=2000
        )
        self.add_item(self.tag_content)

    async def callback(self, interaction: nextcord.Interaction):
        # Get the tag name and content from the modal
        tag_name = self.tag_name.value.lower()
        tag_content = self.tag_content.value

        # Load current tags
        tags = load_tags()

        # Check if tag already exists
        if tag_name in tags:
            await interaction.response.send_message(f"Tag `{tag_name}` already exists!", ephemeral=True)
            return

        # Add the new tag
        tags[tag_name] = tag_content
        save_tags(tags)

        await interaction.response.send_message(f"Tag `{tag_name}` created successfully!", ephemeral=True)


class TagSelectModal(nextcord.ui.Modal):
    """Modal for selecting a tag to edit or delete."""

    def __init__(self, cog: "TagSystem", mode: str):
        super().__init__(title=f"{mode.capitalize()} Tag")
        self.cog = cog
        self.mode = mode

        self.tag_name = nextcord.ui.TextInput(
            label="Tag Name",
            placeholder=f"Enter the tag name to {mode}",
            required=True,
            max_length=100
        )
        self.add_item(self.tag_name)

        if mode == "edit":
            self.tag_content = nextcord.ui.TextInput(
                label="New Tag Content",
                placeholder="Enter the new tag content",
                required=True,
                style=nextcord.TextInputStyle.paragraph,
                max_length=2000
            )
            self.add_item(self.tag_content)

    async def callback(self, interaction: nextcord.Interaction):
        # Get the tag name from the modal
        tag_name = self.tag_name.value.lower()

        # Load current tags
        tags = load_tags()

        # Check if tag exists
        if tag_name not in tags:
            # Try to suggest a similar tag
            similar_tags = difflib.get_close_matches(tag_name, tags.keys(), n=1, cutoff=0.6)
            
            if similar_tags:
                similar_tag = similar_tags[0]
                await interaction.response.send_message(
                    f"Tag `{tag_name}` not found. Did you mean `{similar_tag}`?",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(f"Tag `{tag_name}` not found!", ephemeral=True)
            return

        if self.mode == "edit":
            # Update tag content
            tags[tag_name] = self.tag_content.value
            save_tags(tags)
            await interaction.response.send_message(f"Tag `{tag_name}` updated successfully!", ephemeral=True)
        
        elif self.mode == "delete":
            # Delete the tag
            del tags[tag_name]
            save_tags(tags)
            await interaction.response.send_message(f"Tag `{tag_name}` deleted successfully!", ephemeral=True)


class TagPaginationView(nextcord.ui.View):
    """View for paginated tag list."""

    def __init__(self, tags: List[str], page_size: int = 5):
        super().__init__(timeout=180)
        self.tags = tags
        self.page_size = page_size
        self.current_page = 0
        self.max_pages = (len(tags) - 1) // page_size + 1

        # Disable previous button on first page
        if self.current_page == 0:
            self.children[0].disabled = True
        
        # Disable next button on last page
        if self.current_page >= self.max_pages - 1 or len(tags) <= page_size:
            self.children[1].disabled = True

    @nextcord.ui.button(label="Previous", style=nextcord.ButtonStyle.gray)
    async def previous_button(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        self.current_page = max(0, self.current_page - 1)
        
        # Enable/disable buttons based on current page
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = False

        await self.update_message(interaction)

    @nextcord.ui.button(label="Next", style=nextcord.ButtonStyle.gray)
    async def next_button(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        self.current_page = min(self.max_pages - 1, self.current_page + 1)
        
        # Enable/disable buttons based on current page
        self.children[0].disabled = False
        self.children[1].disabled = self.current_page >= self.max_pages - 1

        await self.update_message(interaction)

    async def update_message(self, interaction: nextcord.Interaction):
        # Get the current page of tags
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, len(self.tags))
        current_tags = self.tags[start_idx:end_idx]

        # Create the embed for the current page
        embed = nextcord.Embed(
            title="Available Tags",
            description="\n".join(f"• `{tag}`" for tag in current_tags),
            color=nextcord.Color.blue()
        )
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_pages}")

        await interaction.response.edit_message(embed=embed, view=self)


class TagSystem(commands.Cog):
    """A tag system with management panel and pagination."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Dictionary to store active suggestion messages
        self.active_suggestions = {}

    @commands.group(name="tag", invoke_without_command=True)
    async def tag(self, ctx: commands.Context, tag_name: str = None):
        """Display a tag or list all tags if no tag name is provided."""
        if tag_name is None:
            await self.display_tags_paginated(ctx)
            return

        tag_name = tag_name.lower()
        tags = load_tags()

        if tag_name in tags:
            await ctx.send(tags[tag_name])
        else:
            # Try to find similar tags for suggestions
            similar_tags = difflib.get_close_matches(tag_name, tags.keys(), n=1, cutoff=0.6)
            
            if similar_tags:
                similar_tag = similar_tags[0]
                suggestion_msg = await ctx.send(
                    f"Tag `{tag_name}` not found. Did you mean `{similar_tag}`? React with ✅ to view or ❌ to cancel."
                )
                
                # Add reactions
                await suggestion_msg.add_reaction("✅")
                await suggestion_msg.add_reaction("❌")
                
                # Store the suggestion data
                self.active_suggestions[suggestion_msg.id] = {
                    "tag": similar_tag,
                    "author_id": ctx.author.id,
                    "expiry": asyncio.get_event_loop().time() + 60  # Expire after 60 seconds
                }
                
                # Schedule cleanup after 60 seconds
                self.bot.loop.create_task(self.cleanup_suggestion(suggestion_msg.id, suggestion_msg))
            else:
                await ctx.send(f"Tag `{tag_name}` not found!")

    @tag.command(name="panel")
    @commands.has_permissions(manage_messages=True)
    async def tag_panel(self, ctx: commands.Context):
        """Open a panel to manage tags."""
        tags = load_tags()
        view = TagManagementView(self, tags)
        
        embed = nextcord.Embed(
            title="Tag Management Panel",
            description="Use the buttons below to manage tags:",
            color=nextcord.Color.green()
        )
        
        await ctx.send(embed=embed, view=view)

    async def display_tags_paginated(self, ctx):
        """Display all tags with pagination."""
        tags = load_tags()
        
        if not tags:
            if isinstance(ctx, nextcord.Interaction):
                await ctx.followup.send("No tags found!")
            else:
                await ctx.send("No tags found!")
            return
        
        # Sort tag names alphabetically
        tag_names = sorted(tags.keys())
        
        # Create paginated view
        view = TagPaginationView(tag_names)
        
        # Get the first page of tags
        current_tags = tag_names[:view.page_size]
        
        embed = nextcord.Embed(
            title="Available Tags",
            description="\n".join(f"• `{tag}`" for tag in current_tags),
            color=nextcord.Color.blue()
        )
        embed.set_footer(text=f"Page 1/{view.max_pages}")
        
        if isinstance(ctx, nextcord.Interaction):
            await ctx.followup.send(embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    async def cleanup_suggestion(self, msg_id: int, message):
        """Clean up an expired suggestion after the timeout."""
        await asyncio.sleep(60)
        if msg_id in self.active_suggestions:
            del self.active_suggestions[msg_id]
            try:
                await message.edit(content=f"Suggestion expired.")
                await message.clear_reactions()
            except (nextcord.NotFound, nextcord.Forbidden):
                pass  # Message might be deleted or bot lacks permissions

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle reactions to suggestion messages."""
        # Ignore bot's own reactions
        if user.bot:
            return
            
        message = reaction.message
        
        # Check if this is a suggestion message
        if message.id not in self.active_suggestions:
            return
            
        suggestion_data = self.active_suggestions[message.id]
        
        # Only the original author can react
        if user.id != suggestion_data["author_id"]:
            return
            
        # Check if reaction is valid
        if str(reaction.emoji) == "✅":
            # User accepted the suggestion
            tag_name = suggestion_data["tag"]
            tags = load_tags()
            
            # Send the tag content
            await message.channel.send(tags[tag_name])
            
            # Clean up the suggestion message
            await message.edit(content=f"Showing tag `{tag_name}`.")
            await message.clear_reactions()
            del self.active_suggestions[message.id]
            
        elif str(reaction.emoji) == "❌":
            # User rejected the suggestion
            await message.edit(content="Tag suggestion cancelled.")
            await message.clear_reactions()
            del self.active_suggestions[message.id]


def setup(bot: commands.Bot):
    """Add the cog to the bot."""
    bot.add_cog(TagSystem(bot))
