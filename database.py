import sqlite3

DB_NAME = "trading_bot.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS youtube_strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_url TEXT,
            strategy_name TEXT,
            timeframe TEXT,
            entry_rules TEXT,
            stop_loss_rules TEXT,
            take_profit_rules TEXT,
            summary TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket INTEGER,
            symbol TEXT,
            trade_type TEXT,
            entry_price REAL,
            stop_loss REAL,
            take_profit REAL,
            thought_process TEXT,
            status TEXT DEFAULT 'OPEN',
            close_price REAL,
            profit REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_post_mortems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER,
            failure_reason TEXT,
            ollama_lesson TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(trade_id) REFERENCES trade_logs(id)
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully.")

if __name__ == "__main__":
    init_db()