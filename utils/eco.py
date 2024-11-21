import sqlite3
import logging
from typing import Optional, List, Dict, Union, Tuple
from datetime import datetime, timedelta
from enum import Enum, auto
from contextlib import contextmanager
from dataclasses import dataclass

@dataclass
class TransactionResult:
    success: bool
    message: Optional[str] = None
    old_balance: Optional[int] = None
    new_balance: Optional[int] = None
    transaction_amount: Optional[int] = None

class TransactionStatus(Enum):
    PENDING = auto()
    COMPLETED = auto()
    FAILED = auto()
    REVERSED = auto()

class EconomyError(Exception):
    def __init__(self, message="An economy-related error occurred", details=None):
        self.message = message
        self.details = details
        super().__init__(self.message)

class TransactionLimitExceededError(EconomyError):
    def __init__(self, limit_type: str, current_amount: int, limit: int):
        message = f"{limit_type} limit exceeded. Current: {current_amount}, Limit: {limit}"
        super().__init__(message, {
            "limit_type": limit_type,
            "current_amount": current_amount,
            "limit": limit
        })

class EconomyManager:
    def __init__(
        self,
        db_path: str = "db/economy.db",
        initial_balance: int = 0,
        max_transaction_history: int = 100,
        logger: Optional[logging.Logger] = None
    ):
        self.db_path = db_path
        self.initial_balance = initial_balance
        self.max_transaction_history = max_transaction_history
        self.logger = logger or logging.getLogger(__name__)
        self._connection = None

    @contextmanager
    def get_connection(self):
        """Context manager for database connections with automatic cleanup."""
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path)
        try:
            yield self._connection
        except Exception as e:
            self.logger.error(f"Database error: {e}")
            raise
        finally:
            if self._connection:
                self._connection.close()
                self._connection = None

    def initialize(self) -> None:
        with self.get_connection() as db:
            cursor = db.cursor()
            
            # Add new status column and indexes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 0,
                    last_daily_claim DATETIME,
                    total_earned INTEGER DEFAULT 0,
                    total_spent INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_activity DATETIME,
                    status TEXT DEFAULT 'active'
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount INTEGER,
                    type TEXT,
                    description TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'completed',
                    reference_id TEXT,
                    metadata TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            """)

            # Add indexes for better query performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_user_timestamp 
                ON transactions(user_id, timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_status 
                ON transactions(status)
            """)

            db.commit()

    async def process_scheduled_operations(self) -> None:
        """Process scheduled operations like interest accrual or recurring rewards."""
        with self.get_connection() as db:
            cursor = db.cursor()
            
            # Example: Apply daily interest to positive balances
            cursor.execute("""
                UPDATE users 
                SET balance = balance + CAST((balance * 0.001) as INTEGER)
                WHERE balance > 0 AND 
                      last_activity <= datetime('now', '-24 hours')
            """)
            
            # Update last activity
            cursor.execute("""
                UPDATE users 
                SET last_activity = CURRENT_TIMESTAMP
                WHERE balance > 0
            """)
            
            db.commit()

    def get_user_statistics(self, user_id: int) -> Dict[str, Union[int, float, str]]:
        """Get comprehensive statistics for a user."""
        with self.get_connection() as db:
            cursor = db.cursor()
            
            cursor.execute("""
                SELECT 
                    u.balance,
                    u.total_earned,
                    u.total_spent,
                    u.created_at,
                    COUNT(t.id) as total_transactions,
                    AVG(CASE WHEN t.amount > 0 THEN t.amount ELSE NULL END) as avg_credit,
                    AVG(CASE WHEN t.amount < 0 THEN t.amount ELSE NULL END) as avg_debit
                FROM users u
                LEFT JOIN transactions t ON u.user_id = t.user_id
                WHERE u.user_id = ?
                GROUP BY u.user_id
            """, (user_id,))
            
            row = cursor.fetchone()
            if not row:
                return {}
                
            return {
                "balance": row[0],
                "total_earned": row[1],
                "total_spent": row[2],
                "account_age_days": (datetime.now() - datetime.fromisoformat(row[3])).days,
                "total_transactions": row[4],
                "average_credit": row[5] or 0,
                "average_debit": row[6] or 0
            }

    def batch_update_balances(
        self,
        updates: List[Tuple[int, int, str]]
    ) -> Dict[str, Union[bool, List[Dict[str, Union[int, str]]]]]:
        """
        Perform batch balance updates efficiently.
        
        Args:
            updates: List of tuples (user_id, amount, description)
        """
        results = []
        with self.get_connection() as db:
            try:
                cursor = db.cursor()
                db.execute("BEGIN")
                
                for user_id, amount, description in updates:
                    # Check wallet limits
                    cursor.execute("""
                        SELECT balance, is_frozen, max_balance 
                        FROM users u
                        LEFT JOIN wallet_limits w ON u.user_id = w.user_id
                        WHERE u.user_id = ?
                    """, (user_id,))
                    
                    row = cursor.fetchone()
                    if not row:
                        current_balance = 0
                        is_frozen = False
                        max_balance = None
                    else:
                        current_balance, is_frozen, max_balance = row
                    
                    if is_frozen:
                        results.append({
                            "user_id": user_id,
                            "success": False,
                            "message": "Account frozen"
                        })
                        continue
                    
                    new_balance = current_balance + amount
                    if max_balance and new_balance > max_balance:
                        results.append({
                            "user_id": user_id,
                            "success": False,
                            "message": "Max balance exceeded"
                        })
                        continue
                    
                    # Update balance
                    cursor.execute("""
                        INSERT INTO users (user_id, balance, total_earned, total_spent)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(user_id) DO UPDATE SET
                        balance = balance + ?,
                        total_earned = CASE WHEN ? > 0 THEN total_earned + ? ELSE total_earned END,
                        total_spent = CASE WHEN ? < 0 THEN total_spent + ABS(?) ELSE total_spent END
                    """, (
                        user_id, new_balance,
                        max(0, amount), abs(min(0, amount)),
                        amount, amount, amount, amount, amount
                    ))
                    
                    results.append({
                        "user_id": user_id,
                        "success": True,
                        "old_balance": current_balance,
                        "new_balance": new_balance
                    })
                
                db.commit()
                return {"success": True, "results": results}
                
            except Exception as e:
                db.rollback()
                self.logger.error(f"Batch update failed: {e}")
                return {"success": False, "message": str(e)}

    def get_leaderboard(
        self,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Union[int, float]]]:
        """Get the top users by balance."""
        with self.get_connection() as db:
            cursor = db.cursor()
            
            cursor.execute("""
                SELECT 
                    user_id,
                    balance,
                    total_earned,
                    total_spent,
                    (SELECT COUNT(*) FROM transactions WHERE user_id = u.user_id) as transaction_count
                FROM users u
                WHERE status = 'active'
                ORDER BY balance DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            return [
                {
                    "user_id": row[0],
                    "balance": row[1],
                    "total_earned": row[2],
                    "total_spent": row[3],
                    "transaction_count": row[4]
                }
                for row in cursor.fetchall()
            ]

def main():
    logging.basicConfig(level=logging.INFO)
    economy = EconomyManager(db_path="db/economy.db")
    economy.initialize()

if __name__ == "__main__":
    main()
