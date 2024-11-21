import sqlite3
import logging
from typing import Optional, List, Dict, Union
from datetime import datetime, timedelta
from enum import Enum, auto

class EconomyError(Exception):
    def __init__(self, message="An economy-related error occurred", details=None):
        self.message = message
        self.details = details
        super().__init__(self.message)

class InsufficientFundsError(EconomyError):
    def __init__(self, current_balance=0, requested_amount=0, user_id=None):
        self.current_balance = current_balance
        self.requested_amount = requested_amount
        self.user_id = user_id
        message = f"Insufficient funds for transaction. Current balance: {current_balance}, Requested: {requested_amount}"
        super().__init__(message, {
            "current_balance": current_balance,
            "requested_amount": requested_amount,
            "user_id": user_id
        })

class TransactionType(Enum):
    CREDIT = auto()
    DEBIT = auto()
    TRANSFER = auto()
    PENALTY = auto()
    REWARD = auto()

class EconomyManager:
    def __init__(self, 
                 db_path: str = "economy.db", 
                 initial_balance: int = 0, 
                 max_transaction_history: int = 100,
                 logger: Optional[logging.Logger] = None):
        self.db_path = db_path
        self.initial_balance = initial_balance
        self.max_transaction_history = max_transaction_history
        self.logger = logger or logging.getLogger(__name__)

    def initialize(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            cursor = db.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 0,
                    last_daily_claim DATETIME,
                    total_earned INTEGER DEFAULT 0,
                    total_spent INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wallet_limits (
                    user_id INTEGER PRIMARY KEY,
                    max_balance INTEGER,
                    daily_withdraw_limit INTEGER,
                    is_frozen BOOLEAN DEFAULT 0,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            """)
            
            db.commit()
            self.logger.info("Economy database initialized successfully")

    def get_balance(self, user_id: int) -> int:
        try:
            with sqlite3.connect(self.db_path) as db:
                cursor = db.cursor()
                cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                return result[0] if result else self.initial_balance
        except Exception as e:
            self.logger.error(f"Error retrieving balance for user {user_id}: {e}")
            return 0

    def update_balance(
        self, 
        user_id: int, 
        amount: int, 
        transaction_type: TransactionType = TransactionType.CREDIT,
        description: str = "Standard Transaction"
    ) -> Dict[str, Union[int, bool]]:
        try:
            with sqlite3.connect(self.db_path) as db:
                cursor = db.cursor()
                
                cursor.execute("SELECT is_frozen, max_balance FROM wallet_limits WHERE user_id = ?", (user_id,))
                restrictions = cursor.fetchone()
                
                if restrictions and restrictions[0]:
                    return {"success": False, "message": "Account is frozen"}
                
                current_balance = self.get_balance(user_id)
                
                if amount < 0 and abs(amount) > current_balance:
                    raise InsufficientFundsError(
                        current_balance=current_balance, 
                        requested_amount=abs(amount), 
                        user_id=user_id
                    )
                
                new_balance = current_balance + amount
                
                if restrictions and restrictions[1] and new_balance > restrictions[1]:
                    return {"success": False, "message": "Max balance limit exceeded"}
                
                cursor.execute("""
                    INSERT INTO users (user_id, balance, total_earned, total_spent) 
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET 
                    balance = balance + ?, 
                    total_earned = total_earned + MAX(0, ?),
                    total_spent = total_spent + MAX(0, ?)
                """, (
                    user_id, new_balance, 
                    max(0, amount), abs(min(0, amount)),
                    amount, 
                    max(0, amount), 
                    abs(min(0, amount))
                ))
                
                cursor.execute("""
                    INSERT INTO transactions (user_id, amount, type, description)
                    VALUES (?, ?, ?, ?)
                """, (user_id, amount, transaction_type.name, description))
                
                cursor.execute("""
                    DELETE FROM transactions 
                    WHERE user_id = ? AND id NOT IN (
                        SELECT id FROM transactions 
                        WHERE user_id = ? 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    )
                """, (user_id, user_id, self.max_transaction_history))
                
                db.commit()
                
                self.logger.info(f"Balance updated for user {user_id}: {amount}")
                
                return {
                    "success": True, 
                    "old_balance": current_balance, 
                    "new_balance": new_balance,
                    "transaction_amount": amount
                }
        
        except InsufficientFundsError as e:
            self.logger.warning(str(e))
            return {"success": False, "message": str(e)}
        
        except Exception as e:
            self.logger.error(f"Unexpected error in balance update: {e}")
            return {"success": False, "message": "Transaction failed"}

    def transfer_funds(
        self, 
        from_user_id: int, 
        to_user_id: int, 
        amount: int, 
        description: str = "User Transfer"
    ) -> Dict[str, Union[int, bool]]:
        if amount <= 0:
            return {"success": False, "message": "Invalid transfer amount"}
        
        with sqlite3.connect(self.db_path) as db:
            try:
                db.execute("BEGIN")
                
                sender_result = self.update_balance(
                    from_user_id, 
                    -amount, 
                    TransactionType.TRANSFER,
                    f"Transfer to user {to_user_id}"
                )
                
                if not sender_result["success"]:
                    db.rollback()
                    return sender_result
                
                receiver_result = self.update_balance(
                    to_user_id, 
                    amount, 
                    TransactionType.TRANSFER,
                    f"Transfer from user {from_user_id}"
                )
                
                if not receiver_result["success"]:
                    self.update_balance(
                        from_user_id, 
                        amount, 
                        TransactionType.CREDIT,
                        "Transfer rollback"
                    )
                    db.rollback()
                    return receiver_result
                
                db.commit()
                
                return {
                    "success": True,
                    "sender_old_balance": sender_result["old_balance"],
                    "sender_new_balance": sender_result["new_balance"],
                    "receiver_old_balance": receiver_result["old_balance"],
                    "receiver_new_balance": receiver_result["new_balance"]
                }
            
            except Exception as e:
                db.rollback()
                self.logger.error(f"Transfer failed: {e}")
                return {"success": False, "message": "Transfer failed"}

    def get_transactions(
        self, 
        user_id: int, 
        limit: int = 10, 
        transaction_type: Optional[TransactionType] = None
    ) -> List[Dict[str, Union[int, str, datetime]]]:
        with sqlite3.connect(self.db_path) as db:
            cursor = db.cursor()
            query = """
                SELECT amount, type, description, timestamp 
                FROM transactions 
                WHERE user_id = ? 
            """
            params = [user_id]
            
            if transaction_type:
                query += " AND type = ?"
                params.append(transaction_type.name)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            return [
                {
                    "amount": row[0], 
                    "type": row[1], 
                    "description": row[2], 
                    "timestamp": datetime.fromisoformat(row[3])
                } 
                for row in cursor.fetchall()
            ]

    def set_wallet_limit(
        self, 
        user_id: int, 
        max_balance: Optional[int] = None, 
        daily_withdraw_limit: Optional[int] = None
    ) -> bool:
        try:
            with sqlite3.connect(self.db_path) as db:
                cursor = db.cursor()
                cursor.execute("""
                    INSERT INTO wallet_limits (user_id, max_balance, daily_withdraw_limit)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET 
                    max_balance = COALESCE(?, max_balance),
                    daily_withdraw_limit = COALESCE(?, daily_withdraw_limit)
                """, (user_id, max_balance, daily_withdraw_limit, max_balance, daily_withdraw_limit))
                db.commit()
                return True
        except Exception as e:
            self.logger.error(f"Error setting wallet limits: {e}")
            return False

def main():
    economy = EconomyManager(db_path="db/economy.db")
    economy.initialize()

if __name__ == "__main__":
    main()
