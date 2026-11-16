import re
import requests
import sqlite3
from youtube_transcript_api import YouTubeTranscriptApi

DB_NAME = "trading_bot.db"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2"  

def extract_video_id(url):
    """
    Extracts video ID from standard watch URLs, short URLs (youtu.be), or embeds.
    """
    pattern = r"(?:v=|\/|youtu\.be\/)([0-9A-Za-z_-]{11})"
    match = re.search(pattern, url)
    return match.group(1) if match else None

def get_transcript(video_id):
    try:

        ytt = YouTubeTranscriptApi()
        
        if hasattr(ytt, "fetch"):
            transcript_list = ytt.fetch(video_id, languages=['en'])
        else:
            transcript_list = ytt.get_transcript(video_id, languages=['en'])

        text_segments = []
        for item in transcript_list:
            if isinstance(item, dict):
                text_segments.append(item.get('text', ''))
            elif hasattr(item, 'text'):
                text_segments.append(item.text)

        return " ".join(text_segments)
    except Exception as e:
        print(f"❌ Error fetching transcript: {e}")
        return None

def analyze_and_store_video(video_url, transcript_text):
    prompt = f"""
    You are an expert Smart Money Concepts (SMC) and ICT (Inner Circle Trader) analyst.
    Below is the transcript of a trading tutorial video.

    TRANSCRIPT:
    {transcript_text[:10000]}

    TASK:
    Analyze the video transcript and extract the key trading concepts.
    Provide a clear, structured breakdown covering:
    1. Strategy Name
    2. Primary Timeframe
    3. Precise Entry Rules (e.g., FVG retest, Order Block touch, Liquidity Sweep)
    4. Stop Loss Placement
    5. Take Profit Rules / Risk-to-Reward Ratio
    6. Brief Summary of the Core Mechanical Concept
    """

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    print("🧠 Sending transcript to Ollama for analysis...")
    try:
        response = requests.post(OLLAMA_URL, json=payload)
        analysis_text = response.json().get("response", "")

        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO youtube_strategies (video_url, strategy_name, summary)
            VALUES (?, ?, ?)
        ''', (video_url, "Extracted SMC Strategy", analysis_text))
        conn.commit()
        conn.close()

        print("\n" + "="*50)
        print("✅ STRATEGY SUCCESSFULLY EXTRACTED & SAVED TO KNOWLEDGE BASE")
        print("="*50)
        print(analysis_text)
    except Exception as e:
        print(f"❌ Failed to reach Ollama: {e}")

def process_youtube_link(url):
    video_id = extract_video_id(url)
    if not video_id:
        print("❌ Invalid YouTube URL.")
        return

    print(f"📹 Fetching transcript for Video ID: {video_id}...")
    transcript = get_transcript(video_id)
    if transcript:
        analyze_and_store_video(url, transcript)

if __name__ == "__main__":
    url_input = input("Paste YouTube URL to ingest: ")
    process_youtube_link(url_input)