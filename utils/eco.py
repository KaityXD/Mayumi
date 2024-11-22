import sqlite3
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timedelta
import json

class EconomySystem:
    """
    A flexible Discord economy system with features like:
    - Banking (balance, transactions)
    - Shop system
    - Inventory management
    - Daily rewards
    - Gambling games
    """
    
    def __init__(self, db_path: str = "economy.db", starting_balance: int = 1000):
        """
        Initialize the economy system.
        
        Args:
            db_path: Path to SQLite database file
            starting_balance: Amount given to new users
        """
        self.conn = sqlite3.connect(db_path)
        self.starting_balance = starting_balance
        self.create_tables()
        self._load_config()

    def _load_config(self):
        """Load default configuration settings"""
        self.config = {
            'daily_reward': 100,
            'daily_streak_bonus': 50,
            'work_min_amount': 50,
            'work_max_amount': 200,
            'work_cooldown': 3600,  # 1 hour in seconds
            'gamble_min': 50,
            'gamble_max': 1000000
        }

    def create_tables(self):
        """Create all required database tables."""
        with self.conn:
            # Users table with more fields
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER NOT NULL DEFAULT 0,
                    bank_balance INTEGER NOT NULL DEFAULT 0,
                    last_daily TIMESTAMP,
                    daily_streak INTEGER DEFAULT 0,
                    last_work TIMESTAMP,
                    inventory TEXT DEFAULT '{}',
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Transactions table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    description TEXT DEFAULT 'Transaction',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Shop items table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS shop (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    price INTEGER NOT NULL,
                    stock INTEGER DEFAULT -1,
                    role_reward TEXT,
                    is_active BOOLEAN DEFAULT 1
                )
            """)

    # === Basic Economy Functions ===
    
    def add_user(self, user_id: int) -> bool:
        """
        Add a new user to the economy system.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            bool: True if new user created, False if user already exists
        """
        try:
            with self.conn:
                self.conn.execute("""
                    INSERT INTO users (user_id, balance)
                    VALUES (?, ?)
                """, (user_id, self.starting_balance))
            return True
        except sqlite3.IntegrityError:
            return False

    def get_balance(self, user_id: int) -> Dict[str, int]:
        """
        Get user's wallet and bank balance.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Dict with wallet and bank balance
        """
        result = self.conn.execute("""
            SELECT balance, bank_balance 
            FROM users 
            WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        if not result:
            self.add_user(user_id)
            return {"wallet": self.starting_balance, "bank": 0}
            
        return {"wallet": result[0], "bank": result[1]}

    def update_balance(self, user_id: int, amount: int, 
                      transaction_type: str = "generic", 
                      description: str = "Update") -> Dict[str, int]:
        """
        Update user's wallet balance.
        
        Args:
            user_id: Discord user ID
            amount: Amount to add (positive) or subtract (negative)
            transaction_type: Category of transaction
            description: Transaction description
            
        Returns:
            Dict with new wallet and bank balance
        """
        balance = self.get_balance(user_id)
        new_balance = balance["wallet"] + amount
        
        if new_balance < 0:
            raise ValueError("Insufficient funds")
            
        with self.conn:
            self.conn.execute("""
                UPDATE users 
                SET balance = ?, last_active = CURRENT_TIMESTAMP 
                WHERE user_id = ?
            """, (new_balance, user_id))
            
            self.conn.execute("""
                INSERT INTO transactions (user_id, amount, type, description)
                VALUES (?, ?, ?, ?)
            """, (user_id, amount, transaction_type, description))
            
        return self.get_balance(user_id)

    # === Banking Functions ===
    
    def deposit(self, user_id: int, amount: int) -> Dict[str, int]:
        """Move money from wallet to bank."""
        balance = self.get_balance(user_id)
        
        if balance["wallet"] < amount:
            raise ValueError("Insufficient funds in wallet")
            
        with self.conn:
            self.conn.execute("""
                UPDATE users 
                SET balance = balance - ?,
                    bank_balance = bank_balance + ?
                WHERE user_id = ?
            """, (amount, amount, user_id))
            
        return self.get_balance(user_id)

    def withdraw(self, user_id: int, amount: int) -> Dict[str, int]:
        """Move money from bank to wallet."""
        balance = self.get_balance(user_id)
        
        if balance["bank"] < amount:
            raise ValueError("Insufficient funds in bank")
            
        with self.conn:
            self.conn.execute("""
                UPDATE users 
                SET balance = balance + ?,
                    bank_balance = bank_balance - ?
                WHERE user_id = ?
            """, (amount, amount, user_id))
            
        return self.get_balance(user_id)

    # === Daily Rewards ===
    
    def claim_daily(self, user_id: int) -> Dict[str, any]:
        """
        Claim daily reward and handle streaks.
        
        Returns dict with:
            - amount: reward amount
            - streak: current streak
            - streak_bonus: bonus for streak
        """
        user = self.conn.execute("""
            SELECT last_daily, daily_streak
            FROM users WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        if not user:
            self.add_user(user_id)
            last_daily = None
            streak = 0
        else:
            last_daily = user[0]
            streak = user[1]

        now = datetime.now()
        
        if last_daily:
            last_daily = datetime.strptime(last_daily, '%Y-%m-%d %H:%M:%S')
            hours_passed = (now - last_daily).total_seconds() / 3600
            
            if hours_passed < 24:
                raise ValueError(f"Daily reward available in {24 - int(hours_passed)} hours")
            
            # Check if streak continues
            if hours_passed <= 48:
                streak += 1
            else:
                streak = 1
        else:
            streak = 1

        # Calculate reward
        base_amount = self.config['daily_reward']
        streak_bonus = self.config['daily_streak_bonus'] * (streak - 1)
        total_amount = base_amount + streak_bonus

        # Update user
        with self.conn:
            self.conn.execute("""
                UPDATE users 
                SET balance = balance + ?,
                    last_daily = ?,
                    daily_streak = ?
                WHERE user_id = ?
            """, (total_amount, now, streak, user_id))

        return {
            "amount": total_amount,
            "streak": streak,
            "streak_bonus": streak_bonus
        }

    # === Inventory System ===
    
    def get_inventory(self, user_id: int) -> Dict:
        """Get user's inventory."""
        result = self.conn.execute("""
            SELECT inventory FROM users WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        if not result:
            return {}
            
        return json.loads(result[0])

    def add_to_inventory(self, user_id: int, item_name: str, quantity: int = 1):
        """Add item to user's inventory."""
        inventory = self.get_inventory(user_id)
        inventory[item_name] = inventory.get(item_name, 0) + quantity
        
        with self.conn:
            self.conn.execute("""
                UPDATE users 
                SET inventory = ?
                WHERE user_id = ?
            """, (json.dumps(inventory), user_id))

    # === Shop System ===
    
    def add_shop_item(self, name: str, price: int, description: str = None, 
                      stock: int = -1, role_reward: str = None):
        """Add item to the shop."""
        with self.conn:
            self.conn.execute("""
                INSERT INTO shop (name, price, description, stock, role_reward)
                VALUES (?, ?, ?, ?, ?)
            """, (name, price, description, stock, role_reward))

    def get_shop_items(self) -> List[Dict]:
        """Get all active shop items."""
        items = self.conn.execute("""
            SELECT name, price, description, stock, role_reward
            FROM shop
            WHERE is_active = 1
        """).fetchall()
        
        return [{
            "name": item[0],
            "price": item[1],
            "description": item[2],
            "stock": item[3],
            "role_reward": item[4]
        } for item in items]

    def buy_item(self, user_id: int, item_name: str) -> Dict:
        """
        Purchase item from shop.
        
        Returns dict with transaction details
        """
        item = self.conn.execute("""
            SELECT price, stock, role_reward
            FROM shop
            WHERE name = ? AND is_active = 1
        """, (item_name,)).fetchone()
        
        if not item:
            raise ValueError("Item not found")
            
        price, stock, role_reward = item
        
        if stock == 0:
            raise ValueError("Item out of stock")
            
        balance = self.get_balance(user_id)
        if balance["wallet"] < price:
            raise ValueError("Insufficient funds")
            
        # Process purchase
        with self.conn:
            # Update stock if limited
            if stock > 0:
                self.conn.execute("""
                    UPDATE shop
                    SET stock = stock - 1
                    WHERE name = ?
                """, (item_name,))
            
            # Add to inventory and remove money
            self.add_to_inventory(user_id, item_name)
            self.update_balance(user_id, -price, "purchase", f"Bought {item_name}")
            
        return {
            "item": item_name,
            "price": price,
            "role_reward": role_reward
        }

    # === Leaderboard ===
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get top users by total wealth (wallet + bank)."""
        return self.conn.execute("""
            SELECT user_id, balance + bank_balance as total
            FROM users
            ORDER BY total DESC
            LIMIT ?
        """, (limit,)).fetchall()

    def close(self):
        """Close database connection."""
        self.conn.close()

# === Example Usage ===
if __name__ == "__main__":
    # Initialize system
    economy = EconomySystem(starting_balance=1000)
    
    # Add some shop items
    economy.add_shop_item("🗡️ Sword", 500, "A mighty weapon", stock=10)
    economy.add_shop_item("👑 VIP Role", 5000, "Exclusive server role", role_reward="VIP")
    
    # Example user interactions
    user_id = 123456789
    
    # Add user and check balance
    economy.add_user(user_id)
    print("Initial balance:", economy.get_balance(user_id))
    
    # Claim daily reward
    try:
        daily = economy.claim_daily(user_id)
        print(f"Daily reward: {daily['amount']} (Streak: {daily['streak']})")
    except ValueError as e:
        print(f"Daily error: {e}")
    
    # Buy an item
    try:
        purchase = economy.buy_item(user_id, "🗡️ Sword")
        print(f"Purchased {purchase['item']} for {purchase['price']}")
    except ValueError as e:
        print(f"Purchase error: {e}")
    
    # Check inventory
    print("Inventory:", economy.get_inventory(user_id))
    
    # Bank operations
    economy.deposit(user_id, 500)
    print("After deposit:", economy.get_balance(user_id))
    
    # Close connection
    economy.close()
