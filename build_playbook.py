import sqlite3
import requests

DB_NAME = "trading_bot.db"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2"

def ensure_playbook_table():
    """Ensures the master_playbook table exists in SQLite."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS master_playbook (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playbook_text TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def build_master_playbook():
    ensure_playbook_table()
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT video_url, strategy_name, summary FROM youtube_strategies")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("⚠️ No raw YouTube strategies found in the database to build a playbook from.")
        return

    print(f"📖 Found {len(rows)} video entries in knowledge base. Merging into Master Playbook...")

    all_notes = ""
    for idx, row in enumerate(rows, 1):
        all_notes += f"\n--- VIDEO LESSON {idx} ({row[1]}) ---\n{row[2]}\n"

    prompt = f"""
    You are a Lead Smart Money Concepts (SMC) & ICT Quantitative Strategist.
    Below are raw trading strategy notes extracted from multiple YouTube tutorial videos. Many concepts may overlap or repeat.

    RAW NOTES:
    {all_notes[:12000]}

    TASK:
    Synthesize ALL the raw notes into ONE unified, concise, non-redundant "Master SMC Trading Playbook".
    Do NOT repeat rules. Merge overlapping ideas into clear confluence checks.

    STRUCTURE THE MASTER PLAYBOOK EXACTLY LIKE THIS:
    1. CORE MARKET STRUCTURE & HTF ALIGNMENT
    2. ENTRY CONFLUENCE CHECKLIST (FVGs, Liquidity Sweeps, Order Blocks)
    3. TIMING & KILLZONES (Best trading windows)
    4. STRICT RISK MANAGEMENT & STOP LOSS RULES
    5. INVALIDATION CONDITIONS (When to HOLD / STAY OUT)
    """

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    try:
        print("🧠 Ollama is synthesizing a unified Master Playbook...")
        response = requests.post(OLLAMA_URL, json=payload)
        master_text = response.json().get("response", "")

    
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO master_playbook (playbook_text) VALUES (?)", (master_text,))
        conn.commit()
        conn.close()

        print("\n" + "="*50)
        print("✅ MASTER SMC PLAYBOOK UPDATED SUCCESSFULLY!")
        print("="*50)
        print(master_text)

    except Exception as e:
        print(f"❌ Failed to generate Master Playbook: {e}")

if __name__ == "__main__":
    build_master_playbook()