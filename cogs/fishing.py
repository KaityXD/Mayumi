import nextcord
from nextcord.ext import commands
import random
from typing import Tuple
import logging
import traceback
from utils.fish_data import tiers, fish_data, modifiers, special_events
from utils.eco import EconomySystem

# Set up logging
import logging
from colorama import Fore, Style

# Define color mapping for log levels
LOG_COLORS = {
    "DEBUG": Fore.BLUE,
    "INFO": Fore.GREEN,
    "WARNING": Fore.YELLOW,
    "ERROR": Fore.RED,
    "CRITICAL": Fore.MAGENTA + Style.BRIGHT,
}

class ColorFormatter(logging.Formatter):
    def format(self, record):
        log_color = LOG_COLORS.get(record.levelname, "")
        record.levelname = f"{log_color}{record.levelname}{Style.RESET_ALL}"
        record.msg = f"{log_color}{record.msg}{Style.RESET_ALL}"
        return super().format(record)

# Configure the logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%y-%m-%d %H:%M",
)
logger = logging.getLogger("Fishing")

# Add the color formatter to the logger
handler = logging.StreamHandler()
handler.setFormatter(ColorFormatter("%(asctime)s [%(levelname)s] %(message)s"))


# Add these classes at the top level of your file, before the FishingSystem class:
class FishButton(nextcord.ui.Button):
    def __init__(self, fishing_cog, original_ctx):
        super().__init__(
            style=nextcord.ButtonStyle.primary,
            label="🎣 Fish Again!",
            custom_id="fish_again"
        )
        self.fishing_cog = fishing_cog
        self.original_ctx = original_ctx

    async def callback(self, interaction: nextcord.Interaction):
        if interaction.user.id != self.original_ctx.author.id:
            await interaction.response.send_message("This button is not for you!", ephemeral=True)
            return

        # Reset cooldown and execute fishing command
        self.original_ctx.command.reset_cooldown(self.original_ctx)
        await interaction.response.defer()
        await self.fishing_cog.fishing(self.original_ctx)

class FishingView(nextcord.ui.View):
    def __init__(self, fishing_cog, ctx):
        super().__init__(timeout=180)  # 3 minute timeout
        self.add_item(FishButton(fishing_cog, ctx))

class FishingSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        try:
            self.economy = EconomySystem(db_path="db/economy.db")
            logger.info("Economy system initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize economy system: {str(e)}")
            raise

        # Verify data is loaded correctly
        logger.info(f"Tiers loaded: {len(tiers)}")
        logger.info(f"Fish data loaded: {len(fish_data)}")
        logger.info(f"Modifiers loaded: {len(modifiers)}")
        logger.info(f"Special events loaded: {len(special_events)}")
        
        self.tiers = tiers
        self.fish_data = fish_data
        self.modifiers = modifiers
        self.special_events = special_events

        # Add relic types and their effects
        self.relic_types = {
            "power_relic": {
                "name": "Power Relic",
                "description": "Doubles fishing earnings",
                "multiplier": 2.0,
                "duration": None  # Permanent until removed
            },
            "lucky_relic": {
                "name": "Lucky Relic",
                "description": "Increases chance of rare fish by 20%",
                "tier_bonus": 0.2,
                "duration": None
            },
            "speed_relic": {
                "name": "Speed Relic",
                "description": "Reduces fishing cooldown by 30%",
                "cooldown_reduction": 0.3,
                "duration": None
            },
            "combo_relic": {
                "name": "Combo Relic",
                "description": "Increases earnings by 20% for each consecutive catch (max 3x)",
                "base_multiplier": 0.2,
                "max_multiplier": 3.0,
                "duration": None
            }
        }
        
        # Track combo counts for combo relic
        self.combo_counts = {}


    def apply_relic_effects(self, user_id: int, tier: str, base_earnings: int) -> Tuple[str, int, float]:
        """Apply relic effects to fishing results"""
        try:
            user_data = self.get_user_data(user_id)
            final_earnings = base_earnings
            cooldown_modifier = 1.0
            tier_modifier = 0

            # Apply Power Relic
            if "power_relic" in user_data or "power relic" in user_data:
                final_earnings *= self.relic_types["power_relic"]["multiplier"]
                
            # Apply Lucky Relic
            if "lucky_relic" in user_data:
                tier_modifier += self.relic_types["lucky_relic"]["tier_bonus"]
                
            # Apply Speed Relic
            if "speed_relic" in user_data:
                cooldown_modifier -= self.relic_types["speed_relic"]["cooldown_reduction"]
                
            # Apply Combo Relic
            if "combo_relic" in user_data:
                if user_id not in self.combo_counts:
                    self.combo_counts[user_id] = 0
                self.combo_counts[user_id] += 1
                combo_bonus = min(
                    self.combo_counts[user_id] * self.relic_types["combo_relic"]["base_multiplier"],
                    self.relic_types["combo_relic"]["max_multiplier"]
                )
                final_earnings = int(final_earnings * (1 + combo_bonus))

            return tier, final_earnings, cooldown_modifier
        except Exception as e:
            logger.error(f"Error applying relic effects: {str(e)}")
            return tier, base_earnings, 1.0

    def get_user_data(self, user_id: int):
        try:
            user_data = self.economy.get_inventory(user_id)
            logger.info(f"User {user_id} data retrieved: {user_data}")
            
            if not user_data:
                logger.info(f"Creating new user {user_id}")
                self.economy.add_user(user_id)
                user_data = self.economy.get_inventory(user_id)
                
            return user_data
        except Exception as e:
            logger.error(f"Error getting user data: {str(e)}")
            raise


    async def create_fish_again_button(self, ctx, original_message):
        """Create a button component for fishing again"""
        button = nextcord.ui.Button(
            style=nextcord.ButtonStyle.primary,
            label="🎣 Fish Again!",
            custom_id="fish_again"
        )
        
        async def button_callback(interaction: nextcord.Interaction):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("This button is not for you!", ephemeral=True)
                return
                
            # Check cooldown
            if self.fishing.is_on_cooldown(ctx):
                retry_after = self.fishing.get_cooldown_retry_after(ctx)
                await interaction.response.send_message(
                    f"Please wait {retry_after:.1f}s before fishing again!", 
                    ephemeral=True
                )
                return
                
            # Execute fishing command
            await interaction.response.defer()
            await self.fishing(ctx)
            
            # Update the original message with new button
            view = nextcord.ui.View()
            view.add_item(await self.create_fish_again_button(ctx, original_message))
            await original_message.edit(view=view)

        button.callback = button_callback
        return button

    def get_fish_by_tier(self, tier: str) -> str:
        try:
            tier_fish = [(name, data) for name, data in self.fish_data.items()
                        if data[2] == tier]
            logger.info(f"Available fish in tier {tier}: {len(tier_fish)}")
            
            if tier_fish:
                return random.choice(tier_fish)[0]
            return "🐟 Small Fish"
        except Exception as e:
            logger.error(f"Error in get_fish_by_tier: {str(e)}")
            return "🐟 Small Fish"

    def apply_modifier(self, fish_name: str, base_value: int) -> Tuple[str, int]:
        try:
            for mod_name, mod_data in self.modifiers.items():
                if random.random() < mod_data['chance']:
                    new_value = int(base_value * mod_data['multiplier'])
                    logger.info(f"Applied modifier {mod_name}: {base_value} -> {new_value}")
                    return f"{mod_data['prefix']} {fish_name} [{mod_name.title()}]", new_value
            return fish_name, base_value
        except Exception as e:
            logger.error(f"Error applying modifier: {str(e)}")
            return fish_name, base_value

    @commands.command(aliases=["fish"])
    @commands.cooldown(1, 20, commands.BucketType.user)
    async def fishing(self, ctx):
        try:
            user_id = ctx.author.id
            user_name = ctx.author.display_name
            logger.info(f"Fishing command initiated by user {user_name}")
            
            data = self.get_user_data(user_id)
            logger.info(f"User data retrieved: {data}")

            if 'rod' not in data:
                await ctx.reply("You need a fishing rod! Buy one from the store.")
                return

            # Get fish tier
            tier = random.choices(
                list(self.tiers.keys()),
                weights=list(self.tiers.values()),
                k=1
            )[0]
            logger.info(f"Selected tier: {tier}")

            # Get fish and calculate earnings
            caught_fish = self.get_fish_by_tier(tier)
            logger.info(f"Caught fish: {caught_fish}")

            min_price, max_price, _ = self.fish_data[caught_fish]
            base_earnings = random.randint(min_price, max_price)
            logger.info(f"Base earnings: {base_earnings}")

            final_fish, final_earnings = self.apply_modifier(caught_fish, base_earnings)
            logger.info(f"Final fish: {final_fish}, Final earnings: {final_earnings}")

            # Handle special events
            special_event = None
            if random.random() < 0.10:
                special_event = random.choice(self.special_events)
                logger.info(f"Special event triggered: {special_event}")
                
                if "Double" in special_event:
                    final_earnings *= 2
                elif "Triple" in special_event:
                    final_earnings *= 3
                elif "Extra" in special_event:
                    bonus = int(special_event.split()[special_event.split().index("coins!") - 1])
                    final_earnings += bonus
                logger.info(f"Earnings after special event: {final_earnings}")

            # Update user's balance
            try:
                logger.info(f"final_earnings before relic: {final_earnings}")
                if "power relic" in data:
                    final_earnings *= 2
                    logger.info("user have relic in inv *2 money")
                self.economy.update_balance(user_id, final_earnings, "fishing", f"Caught {final_fish}")
                logger.info(f"Balance updated for user {user_id}: +{final_earnings}")
            except Exception as e:
                logger.error(f"Failed to update balance: {str(e)}")
                await ctx.reply("❌ Error updating balance. Please try again.")
                return

            # Create and send embed
            embed = nextcord.Embed(
                title="🎣 Fishing Results",
                color=0x00ff00
            )
            embed.add_field(name="You caught", value=final_fish, inline=False)
            embed.add_field(name="Earnings", value=f"💰 {final_earnings}", inline=False)

            if special_event:
                embed.add_field(name="Special Event!", value=special_event, inline=False)

            # Get fishing stats from inventory
            fishing_stats = data.get('fishing_stats', {'total_caught': 0})
            if fishing_stats['total_caught'] % 10 == 0 and fishing_stats['total_caught'] > 0:
                embed.add_field(
                    name="Milestone!",
                    value=f"You've caught {fishing_stats['total_caught']} fish in total! 🎉",
                    inline=False
                )

            view = FishingView(self, ctx)
            await ctx.reply(embed=embed, view=view) 
        except Exception as e:
            logger.error(f"Error in fishing command: {traceback.format_exc()}")
            await ctx.reply(f"❌ An error occurred while fishing. Please try again later.")



    @commands.command(name="fishinfo")
    async def fishing_info(self, ctx):
        try:
            embed = nextcord.Embed(
                title="🎣 Fishing Information",
                description="Fish varieties and their catch rates:",
                color=0x00ff00
            )

            for tier, chance in self.tiers.items():
                tier_fish = [f"{name} ({data[0]}-{data[1]} coins)"
                            for name, data in self.fish_data.items()
                            if data[2] == tier]
                if tier_fish:
                    embed.add_field(
                        name=f"{tier.title()} Tier ({chance*100}% chance)",
                        value="\n".join(tier_fish),
                        inline=False
                    )

            mod_text = "\n".join([
                f"{data['prefix']} {name.title()}: {data['chance']*100}% chance for {data['multiplier']}x value"
                for name, data in self.modifiers.items()
            ])
            embed.add_field(name="Special Modifiers", value=mod_text, inline=False)
            embed.add_field(
                name="Special Events",
                value="10% chance for special events to occur while fishing!",
                inline=False
            )

            await ctx.reply(embed=embed)
        except Exception as e:
            logger.error(f"Error in fishing_info command: {str(e)}")
            await ctx.reply("❌ An error occurred while fetching fishing information.")

def setup(bot):
    try:
        bot.add_cog(FishingSystem(bot))
        logger.info("FishingSystem cog loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load FishingSystem cog: {str(e)}")
        raise
