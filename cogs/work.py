import random
from typing import Dict, TypedDict
from nextcord.ext import commands
from nextcord.ext.commands import CooldownMapping, BucketType, CommandOnCooldown
from datetime import datetime
from utils.eco import EconomySystem

class TaskResponse(TypedDict):
    prompt: str
    answer: str
    reward_multiplier: float

class Work(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.economy = EconomySystem(db_path="db/economy.db")
        self._load_tasks()

    def _load_tasks(self) -> None:
        """Load work tasks with difficulty ratings"""
        self.trivia_questions = [
            {
                'question': "What is the capital of France?",
                'answer': "paris",
                'difficulty': 1.0
            },
            {
                'question': "How many sides does a hexagon have?",
                'answer': "6",
                'difficulty': 1.0
            },
            {
                'question': "What is the chemical symbol for water?",
                'answer': "h2o",
                'difficulty': 1.2
            },
            {
                'question': "What is the square root of 144?",
                'answer': "12",
                'difficulty': 1.3
            },
                    
            {
                "question": "What is the largest planet in our solar system?",
                "answer": "Jupiter",
                "difficulty": 1
            },
            {
                "question": "What is the capital of the United States?",
                "answer": "Washington, D.C.",
                "difficulty": 1
            },
            {
                "question": "What is the color of the sky?",
                "answer": "Blue",
                "difficulty": 1
            },
            {
                "question": "What is the chemical symbol for water?",
                "answer": "H2O",
                "difficulty": 2
            },
            {
                "question": "Who painted the Mona Lisa?",
                "answer": "Leonardo da Vinci",
                "difficulty": 2
            },
            {
                "question": "What is the largest country in South America?",
                "answer": "Brazil",
                "difficulty": 2
            },
            {
                "question": "What is the capital of Australia?",
                "answer": "Canberra",
                "difficulty": 3
            },
            {
                "question": "What is the highest mountain in Africa?",
                "answer": "Mount Kilimanjaro",
                "difficulty": 3
            },
            {
                "question": "What is the largest ocean in the world?",
                "answer": "Pacific Ocean",
                "difficulty": 3
            }


        ]
        
        self.typing_words = [
            {'word': 'hello', 'difficulty': 1.0},
            {'word': 'discord', 'difficulty': 1.2},
            {'word': 'economy', 'difficulty': 1.3},
            {'word': 'cryptocurrency', 'difficulty': 1.5},
            {'word': 'leaderboard', 'difficulty': 1.4},
            {'word': 'Pneumonoultramicroscopicsilicovolcanoconiosis', 'difficulty': 5},
            {'word': 'antidisestablishmentarianism', 'difficulty': 1.7},
            {'word': 'anime', 'difficulty': 1},
            {'word': 'cybertruck', 'difficulty': 1.2},
            {'word': 'hello', 'difficulty': 1.2},          
            {"word": "quixotic", "difficulty": 3},
            {"word": "serendipity", "difficulty": 3},
            {"word": "onomatopoeia", "difficulty": 3},
            {"word": "schadenfreude", "difficulty": 3},
            {"word": "petrichor", "difficulty": 2},
            {"word": "ephemeral", "difficulty": 2},
            {"word": "ubiquitous", "difficulty": 2},
            {"word": "melancholy", "difficulty": 1},
            {"word": "nostalgia", "difficulty": 1},
            {"word": "euphoria", "difficulty": 1}

        ]

    @commands.command(name="work")
    @commands.cooldown(3, 60, BucketType.user)
    async def work(self, ctx: commands.Context):
        """Work to earn money through interactive mini-games"""
        user_id = ctx.author.id

        # Generate task and send prompt
        task = self.generate_task()
        await ctx.send(f"{task['prompt']}\n\n*You have 15 seconds to respond!*")

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            msg = await self.bot.wait_for('message', timeout=15.0, check=check)
            
            if str(msg.content).strip().lower() == str(task['answer']).lower():
                # Calculate earnings with difficulty multiplier
                base_amount = random.randint(
                    self.economy.config['work_min_amount'],
                    self.economy.config['work_max_amount']
                )
                earned_amount = int(base_amount * task['reward_multiplier'])
                
                try:
                    # Update balance using existing economy system
                    self.economy.update_balance(
                        user_id,
                        earned_amount,
                        transaction_type="work",
                        description="Work reward"
                    )
                    
                    await ctx.send(
                        f"🎉 Great work! You earned `{earned_amount}` coins! "
                        f"(Difficulty multiplier: {task['reward_multiplier']}x)"
                    )
                except Exception as e:
                    await ctx.send("❌ There was an error processing your reward. Please try again later.")
                    raise e
            else:
                await ctx.send(
                    f"❌ That's incorrect! The answer was `{task['answer']}`."
                )
                
        except TimeoutError:
            await ctx.send("❌ Time's up! You took too long to respond.")

    def generate_task(self) -> TaskResponse:
        """Generate a random work task with difficulty multipliers"""
        task_type = random.choices(
            ['math', 'typing', 'trivia'],
            weights=[0.4, 0.3, 0.3],
            k=1
        )[0]

        if task_type == 'math':
            difficulty = random.uniform(1.0, 1.5)  # Reduced max difficulty
            max_num = int(20 * difficulty)
            a, b = random.randint(1, max_num), random.randint(1, max_num)
            
            return {
                'prompt': f"🧮 Solve this math problem: **{a} + {b}**",
                'answer': str(a + b),
                'reward_multiplier': difficulty
            }
            
        elif task_type == 'typing':
            task = random.choice(self.typing_words)
            return {
                'prompt': f"⌨️ Type this word exactly: **{task['word']}**",
                'answer': task['word'],
                'reward_multiplier': task['difficulty']
            }
            
        else:  # trivia
            question = random.choice(self.trivia_questions)
            return {
                'prompt': f"❓ {question['question']}",
                'answer': question['answer'],
                'reward_multiplier': question['difficulty']
            }

    @work.error
    async def work_error(self, ctx: commands.Context, error):
        """Handle work command errors"""
        if isinstance(error, CommandOnCooldown):
            remaining_time = error.retry_after
            hours = int(remaining_time // 3600)
            minutes = int((remaining_time % 3600) // 60)
            seconds = int(remaining_time % 60)
            pass
        else:
            # Log the error but don't raise it to prevent crashes
            print(f"Error in work command: {str(error)}")
            await ctx.send("❌ Something went wrong with the work command. Please try again later.")

def setup(bot):
    bot.add_cog(Work(bot))
