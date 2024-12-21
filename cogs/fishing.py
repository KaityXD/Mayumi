import nextcord
from nextcord.ext import commands
import random
from typing import Tuple
from utils.fish_data import tiers, fish_data, modifiers, special_events
from utils.eco import EconomySystem

ENCHANTMENTS = {
    'luck': {
        'name': 'Luck',
        'description': 'Increases chance of better tier fish',
        'max_level': 5,
        'base_cost': 10000,
        'tier_boost_per_level': 0.05
    },
    'fortune': {
        'name': 'Fortune',
        'description': 'Increases fish value',
        'max_level': 5,
        'base_cost': 15000,
        'value_multiplier_per_level': 0.1
    },
    'efficiency': {
        'name': 'Efficiency',
        'description': 'Reduces fishing cooldown',
        'max_level': 3,
        'base_cost': 20000,
        'cooldown_reduction_per_level': 0.2
    }
}

class FishingSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.economy = EconomySystem(db_path="db/economy.db")
        self.tiers = tiers
        self.fish_data = fish_data
        self.modifiers = modifiers
        self.special_events = special_events

    def get_user_data(self, user_id: int):
        user_data = self.economy.get_inventory(user_id)
        if not user_data:
            self.economy.add_user(user_id)
            user_data = self.economy.get_inventory(user_id)
        return user_data

    def calculate_enchantment_cost(self, enchant_type: str, current_level: int) -> int:
        base_cost = ENCHANTMENTS[enchant_type]['base_cost']
        return base_cost * (current_level + 1) * 2

    def apply_enchantments(self, tier_chances: dict, base_value: int, enchantments: dict) -> Tuple[dict, int]:
        luck_level = enchantments.get('luck', 0)
        if luck_level > 0:
            boost = ENCHANTMENTS['luck']['tier_boost_per_level'] * luck_level
            for tier in ['rare', 'epic', 'legendary']:
                if tier in tier_chances:
                    tier_chances[tier] *= (1 + boost)

        fortune_level = enchantments.get('fortune', 0)
        if fortune_level > 0:
            value_boost = 1 + (ENCHANTMENTS['fortune']['value_multiplier_per_level'] * fortune_level)
            base_value = int(base_value * value_boost)

        return tier_chances, base_value

    def get_fish_by_tier(self, tier: str) -> str:
        tier_fish = [(name, data) for name, data in self.fish_data.items()
                    if data[2] == tier]
        if tier_fish:
            return random.choice(tier_fish)[0]
        return "🐟 Small Fish"

    def apply_modifier(self, fish_name: str, base_value: int) -> Tuple[str, int]:
        for mod_name, mod_data in self.modifiers.items():
            if random.random() < mod_data['chance']:
                new_value = int(base_value * mod_data['multiplier'])
                return f"{mod_data['prefix']} {fish_name} [{mod_name.title()}]", new_value
        return fish_name, base_value

    @commands.command(name="enchant")
    async def enchant_rod(self, ctx, enchant_type: str = None):
        if not enchant_type:
            await self.show_enchantments(ctx)
            return

        enchant_type = enchant_type.lower()
        if enchant_type not in ENCHANTMENTS:
            await ctx.send(f"Invalid enchantment type. Available enchantments: {', '.join(ENCHANTMENTS.keys())}")
            return

        user_id = ctx.author.id
        data = self.get_user_data(user_id)

        if 'rod' not in data.get('inventory', {}):
            await ctx.send("You need a fishing rod first!")
            return

        current_level = data.get('rod_enchantments', {}).get(enchant_type, 0)
        if current_level >= ENCHANTMENTS[enchant_type]['max_level']:
            await ctx.send(f"Your rod already has maximum level of {enchant_type}!")
            return

        cost = self.calculate_enchantment_cost(enchant_type, current_level)
        balance = self.economy.get_balance(user_id)["wallet"]
        if balance < cost:
            await ctx.send(f"You need {cost} coins to enchant your rod with {enchant_type}!")
            return

        enchantments = data.get('rod_enchantments', {})
        enchantments[enchant_type] = current_level + 1

        self.economy.update_balance(user_id, -cost, "enchant", f"Enchanted rod with {enchant_type}")
        data['rod_enchantments'] = enchantments
        self.economy.add_to_inventory(user_id, 'rod_enchantments', enchantments)

        embed = nextcord.Embed(
            title="🎣 Rod Enchanted!",
            description=f"Successfully enchanted your rod with {ENCHANTMENTS[enchant_type]['name']}!",
            color=0x00ff00
        )
        embed.add_field(name="New Level", value=f"{current_level + 1}/{ENCHANTMENTS[enchant_type]['max_level']}")
        embed.add_field(name="Cost", value=f"💰 {cost}")
        await ctx.send(embed=embed)

    @commands.command(name="enchantments")
    async def show_enchantments(self, ctx):
        user_id = ctx.author.id
        data = self.get_user_data(user_id)
        current_enchants = data.get('rod_enchantments', {})

        embed = nextcord.Embed(
            title="🎣 Rod Enchantments",
            description="Current enchantments and available upgrades:",
            color=0x00ff00
        )

        for enchant_type, enchant_data in ENCHANTMENTS.items():
            current_level = current_enchants.get(enchant_type, 0)
            next_cost = self.calculate_enchantment_cost(enchant_type, current_level) if current_level < enchant_data['max_level'] else "MAX"

            value = f"Level: {current_level}/{enchant_data['max_level']}\n"
            value += f"Effect: {enchant_data['description']}\n"
            value += f"Next upgrade: {'MAX' if current_level >= enchant_data['max_level'] else f'💰 {next_cost}'}"

            embed.add_field(
                name=f"{enchant_data['name']}",
                value=value,
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command(aliases=["fish"])
    @commands.cooldown(5, 3, commands.BucketType.user)
    async def fishing(self, ctx):
        user_id = ctx.author.id
        data = self.get_user_data(user_id)
        # print(f"[Mayumi]: Here your data {data}")

        if 'rod' not in data.get():
            await ctx.send("You need a fishing rod! Buy one from the store.")
            return

        enchanted_tiers = dict(self.tiers)
        base_earnings = 0
        enchanted_tiers, base_earnings = self.apply_enchantments(
            enchanted_tiers,
            base_earnings,
            data.get('rod_enchantments', {})
        )

        tier = random.choices(
            list(enchanted_tiers.keys()),
            weights=list(enchanted_tiers.values()),
            k=1
        )[0]

        caught_fish = self.get_fish_by_tier(tier)
        min_price, max_price, _ = self.fish_data[caught_fish]
        base_earnings = random.randint(min_price, max_price)

        final_fish, final_earnings = self.apply_modifier(caught_fish, base_earnings)

        special_event = None
        if random.random() < 0.10:
            special_event = random.choice(self.special_events)
            if "Double" in special_event:
                final_earnings *= 2
            elif "Triple" in special_event:
                final_earnings *= 3
            elif "Extra" in special_event:
                bonus = int(special_event.split()[special_event.split().index("coins!") - 1])
                final_earnings += bonus

        fishing_stats = data.get('fishing_stats', {'total_caught': 0, 'best_catch': None, 'best_earnings': 0})
        fishing_stats['total_caught'] += 1
        if final_earnings > fishing_stats.get('best_earnings', 0):
            fishing_stats['best_earnings'] = final_earnings
            fishing_stats['best_catch'] = final_fish

        self.economy.update_balance(user_id, final_earnings, "fishing", f"Caught {final_fish}")
        data['fishing_stats'] = fishing_stats
        self.economy.add_to_inventory(user_id, 'fishing_stats', fishing_stats)

        embed = nextcord.Embed(
            title="🎣 Fishing Results",
            color=0x00ff00
        )
        embed.add_field(name="You caught", value=final_fish, inline=False)
        embed.add_field(name="Earnings", value=f"💰 {final_earnings}", inline=False)

        if special_event:
            embed.add_field(name="Special Event!", value=special_event, inline=False)

        if fishing_stats['total_caught'] % 10 == 0:
            embed.add_field(
                name="Milestone!",
                value=f"You've caught {fishing_stats['total_caught']} fish in total! 🎉",
                inline=False
            )

        # Apply cooldown reduction based on efficiency enchantment
        efficiency_level = data.get('rod_enchantments', {}).get('efficiency', 0)
        if efficiency_level > 0:
            cooldown_reduction = ENCHANTMENTS['efficiency']['cooldown_reduction_per_level'] * efficiency_level
            cooldown = max(3 - cooldown_reduction, 0)  # Ensure cooldown is not negative
            self.fishing._buckets._cooldown.update_rate_limit(ctx.message, cooldown)
            self.fishing.reset_cooldown(ctx)
            self.fishing._buckets.update_rate_limit(ctx)

        await ctx.send(embed=embed)

    @commands.command(name="fishstats")
    async def fishing_stats(self, ctx):
        user_id = ctx.author.id
        data = self.get_user_data(user_id)
        stats = data.get('fishing_stats', {})

        embed = nextcord.Embed(
            title=f"🎣 {ctx.author.name}'s Fishing Statistics",
            color=0x00ff00
        )

        embed.add_field(name="Total Fish Caught", value=stats.get('total_caught', 0))
        embed.add_field(name="Best Catch", value=stats.get('best_catch', 'None yet!'))
        embed.add_field(name="Highest Earnings", value=f"💰 {stats.get('best_earnings', 0)}")

        await ctx.send(embed=embed)

    @commands.command(name="fishinfo")
    async def fishing_info(self, ctx):
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

        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(FishingSystem(bot))