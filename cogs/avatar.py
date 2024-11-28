import nextcord
from nextcord.ext import commands
from nextcord import IntegrationType, Interaction, InteractionContextType
from typing import Union
from io import BytesIO
import aiohttp
from PIL import Image, ImageOps, ImageFilter

class Avatar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    async def get_avatar(self, user: nextcord.User, size: int = 1024) -> str:
        """Get user's avatar URL with specified size"""
        format = 'gif' if user.display_avatar.is_animated() else 'png'
        return user.display_avatar.with_size(size).url

    @nextcord.slash_command(name="avatar", description="Show user's avatar")
    async def slash_avatar(
        self, 
        interaction: nextcord.Interaction,
        user: nextcord.Member = nextcord.SlashOption(required=False, description="The user whose avatar to show"),
        size: int = nextcord.SlashOption(required=False, description="Size of the avatar (max 4096)", default=1024)
    ):
        await self.show_avatar(interaction, user or interaction.user, size)

    @commands.command(name="avatar", aliases=["av", "pfp"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def prefix_avatar(
        self, 
        ctx: commands.Context, 
        user: Union[nextcord.Member, nextcord.User] = None,
        size: int = 1024
    ):
        """
        Show user's avatar with various options
        
        Parameters
        -----------
        user: The user whose avatar to show (defaults to command author)
        size: Size of the avatar (max 4096)
        """
        await self.show_avatar(ctx, user or ctx.author, size)

    async def show_avatar(
        self,
        ctx: Union[nextcord.Interaction, commands.Context],
        user: Union[nextcord.Member, nextcord.User],
        size: int = 1024
    ):
        """Common function to handle avatar display for both slash and prefix commands"""
        if size > 4096:
            response = "Maximum size is 4096!"
            if isinstance(ctx, nextcord.Interaction):
                await ctx.response.send_message(response)
            else:
                await ctx.send(response)
            return

        embed = nextcord.Embed(color=nextcord.Color.blue())
        embed.set_author(name=f"{user}'s Avatar", icon_url=user.display_avatar.url)
        
        avatar_url = await self.get_avatar(user, size)
        embed.set_image(url=avatar_url)
        
        # Add avatar links
        formats = ['png', 'jpg', 'webp']
        if user.display_avatar.is_animated():
            formats.append('gif')
            
        links = []
        for fmt in formats:
            url = user.display_avatar.with_format(fmt).url
            links.append(f"[{fmt.upper()}]({url})")
            
        embed.add_field(name="Links", value=" | ".join(links), inline=False)
        
        # Add some user info
        embed.add_field(
            name="User Info",
            value=f"**ID:** {user.id}\n**Bot:** {'Yes' if user.bot else 'No'}\n**Created:** <t:{int(user.created_at.timestamp())}:R>",
            inline=False
        )
        
        # Create button view
        view = nextcord.ui.View()
        
        # Server avatar button (if applicable)
        if isinstance(user, nextcord.Member) and user.guild_avatar:
            view.add_item(
                nextcord.ui.Button(
                    label="Server Avatar",
                    url=user.guild_avatar.url,
                    style=nextcord.ButtonStyle.url
                )
            )
            
        # Global avatar button
        view.add_item(
            nextcord.ui.Button(
                label="Global Avatar",
                url=user.display_avatar.url,
                style=nextcord.ButtonStyle.url
            )
        )

        if isinstance(ctx, nextcord.Interaction):
            await ctx.response.send_message(embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    @nextcord.slash_command(name="serveravatar", description="Show member's server avatar")
    async def slash_server_avatar(
        self,
        interaction: nextcord.Interaction,
        member: nextcord.Member = nextcord.SlashOption(required=False, description="The member whose server avatar to show")
    ):
        await self.show_server_avatar(interaction, member or interaction.user)

    @commands.command(name="serveravatar", aliases=["sav", "guildavatar"])
    @commands.guild_only()
    async def prefix_server_avatar(
        self,
        ctx: commands.Context,
        member: nextcord.Member = None
    ):
        """Show a member's server-specific avatar if they have one"""
        await self.show_server_avatar(ctx, member or ctx.author)

    async def show_server_avatar(
        self,
        ctx: Union[nextcord.Interaction, commands.Context],
        member: nextcord.Member
    ):
        """Common function to handle server avatar display"""
        if not member.guild_avatar:
            response = f"{member} doesn't have a server-specific avatar!"
            if isinstance(ctx, nextcord.Interaction):
                await ctx.response.send_message(response)
            else:
                await ctx.send(response)
            return
            
        embed = nextcord.Embed(color=nextcord.Color.blue())
        embed.set_author(name=f"{member}'s Server Avatar", icon_url=member.guild_avatar.url)
        embed.set_image(url=member.guild_avatar.url)
        
        # Add format links
        formats = ['png', 'jpg', 'webp']
        if member.guild_avatar.is_animated():
            formats.append('gif')
            
        links = []
        for fmt in formats:
            url = member.guild_avatar.with_format(fmt).url
            links.append(f"[{fmt.upper()}]({url})")
            
        embed.add_field(name="Links", value=" | ".join(links), inline=False)

        if isinstance(ctx, nextcord.Interaction):
            await ctx.response.send_message(embed=embed)
        else:
            await ctx.send(embed=embed)

    @nextcord.slash_command(
        name="banner", 
        description="Show user's banner",
        integration_types=[
                IntegrationType.user_install,
                IntegrationType.guild_install,
            ]
    )
    async def slash_banner(
        self,
        interaction: nextcord.Interaction,
        user: nextcord.User = nextcord.SlashOption(required=False, description="The user whose banner to show")
    ):
        await self.show_banner(interaction, user or interaction.user)

    @commands.command(name="banner")
    async def prefix_banner(
        self,
        ctx: commands.Context,
        user: Union[nextcord.Member, nextcord.User] = None
    ):
        """Show a user's banner if they have one"""
        await self.show_banner(ctx, user or ctx.author)

    async def show_banner(
        self,
        ctx: Union[nextcord.Interaction, commands.Context],
        user: Union[nextcord.Member, nextcord.User]
    ):
        """Common function to handle banner display"""
        try:
            fetched_user = await self.bot.fetch_user(user.id)
            if not fetched_user.banner:
                response = f"{user} doesn't have a banner!"
                if isinstance(ctx, nextcord.Interaction):
                    await ctx.response.send_message(response)
                else:
                    await ctx.send(response)
                return
                
            embed = nextcord.Embed(color=nextcord.Color.blue())
            embed.set_author(name=f"{user}'s Banner", icon_url=user.display_avatar.url)
            embed.set_image(url=fetched_user.banner.url)
            
            # Add format links
            formats = ['png', 'jpg', 'webp']
            if fetched_user.banner.is_animated():
                formats.append('gif')
                
            links = []
            for fmt in formats:
                url = fetched_user.banner.with_format(fmt).url
                links.append(f"[{fmt.upper()}]({url})")
                
            embed.add_field(name="Links", value=" | ".join(links), inline=False)
            
            if isinstance(ctx, nextcord.Interaction):
                await ctx.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            
        except nextcord.HTTPException:
            response = "Failed to fetch user's banner."
            if isinstance(ctx, nextcord.Interaction):
                await ctx.response.send_message(response)
            else:
                await ctx.send(response)

def setup(bot):
    bot.add_cog(Avatar(bot))

"""
import nextcord
from nextcord import IntegrationType, Interaction, InteractionContextType, Embed
from nextcord.ext import commands

class AvatarCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @nextcord.slash_command(
        description="Show the avatar of a user or yourself.",
        integration_types=[
            IntegrationType.user_install,
            IntegrationType.guild_install,
        ],
        contexts=[
            InteractionContextType.guild,
            InteractionContextType.bot_dm,
            InteractionContextType.private_channel,
        ],
    )
    async def ava(self, interaction: Interaction, user: nextcord.User = None):
        target_user = user or interaction.user
        embed = Embed(title=f"{target_user.name}'s Avatar", color=nextcord.Color.blurple())
        embed.set_image(url=target_user.avatar.url)
        await interaction.response.send_message(embed=embed)

def setup(bot):
    bot.add_cog(AvatarCog(bot))
    
"""
