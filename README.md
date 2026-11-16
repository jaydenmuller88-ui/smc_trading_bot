# SMC & ICT Algorithmic Trading Bot

An automated quantitative trading system built in Python for MetaTrader 5. The bot executes Smart Money Concepts (SMC) and Inner Circle Trader (ICT) strategies during high-liquidity session killzones, calculates dynamic equity-based risk parameters, logs trade rationale via a local LLM (Ollama), and includes a preprocessing utility to extract trading rules directly from educational YouTube videos.

## Core Features

* **Session Killzone Filtering:** Restricts execution strictly to high-volatility London and New York UTC time windows.
* **SMC/ICT Signal Engine:** Automatically scans intraday timeframes for Fair Value Gaps (FVGs), market structure breaks, and institutional order block zones.
* **Dynamic Risk Management:** Automatically calculates lot sizes based on account equity percentage, exact stop-loss distance, and broker tick values.
* **Local AI Trade Journaling:** Connects to a local Ollama instance to generate structured post-trade commentary and record records in JSONL format without external API dependencies.
* **Automated YouTube Strategy Extractor:** Parses educational transcripts to dynamically ingest SMC/ICT rule variations.

## Architecture & Project Structure

```text
smc_trading_bot/
├── core/
│   ├── mt5_connector.py    # MetaTrader 5 session initialization & data fetching
│   ├── risk_manager.py     # Lot sizing, stop-loss, and take-profit calculation
│   └── order_manager.py    # Trade execution & position lifecycle handling
├── strategy/
│   ├── killzones.py        # London & New York session time filters
│   └── smc_engine.py       # FVG & market structure evaluation logic
├── extractor/
│   └── youtube_parser.py   # Transcript fetcher & Ollama rule extraction utility
├── journal/
│   └── ollama_logger.py    # Local LLM trade rationale and logging engine
├── settings.example.json   # Configuration template for MT5 and Ollama
├── requirements.txt
├── .gitignore
└── README.md
