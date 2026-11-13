# NBS Inflation Agent 🤖📊

An automated, containerized data pipeline that monitors the Nigerian National Bureau of Statistics (NBS) portal for new **Premium Motor Spirit (PMS) price reports**, extracts state-by-state pricing data using Generative AI, and broadcasts formatted analytics to a Telegram channel.

---

## 📖 Table of Contents
1. [System Architecture](#-system-architecture)
2. [Prerequisites](#-prerequisites)
3. [File Structure](#-file-structure)
4. [Environment Configuration](#️-environment-configuration)
5. [Deployment & Installation](#-deployment--installation)
6. [n8n Workflow Configuration](#-n8n-workflow-configuration)
7. [Troubleshooting & Maintenance](#-troubleshooting--maintenance)

---

## 🏗 System Architecture

The application is decoupled into a robust, two-stage orchestration flow using **n8n** as the orchestrator, **Python** for heavy lifting, and **Google Gemini** for intelligent data extraction.

1. **Orchestration (n8n):** A monthly cron schedule triggers the pipeline.
2. **Ingestion (`scraper.py`):** The scraper dynamically parses the NBS portal, probes the top 4 newest resources (acting as a safety net for staggered uploads), downloads new ZIP archives, extracts the PDFs, and deduplicates against local storage.
3. **Extraction (`parser.py`):** The PDF is passed to Gemini 2.5 Flash using strict Pydantic schema validation. It extracts publication dates, categories, state-by-state prices, and MoM/YoY percentage changes.
4. **Dispatch (Telegram):** n8n formats the structured JSON into a highly readable HTML summary and dispatches it to the configured Telegram chat.

---

## 🛠 Prerequisites

- **Docker** and **Docker Compose**
- **n8n** (Deployed via Docker)
- **Google Gemini API Key** (Obtain from [Google AI Studio](https://aistudio.google.com/))
- **Telegram Bot Token & Chat ID** (Create via [@BotFather](https://t.me/BotFather))

---

## 📂 File Structure

```text
nbs-inflation-agent/
│
├── .env                     # Environment variables (secrets)
├── .env.example             # Template for environment variables
├── docker-compose.yml       # Docker orchestration
├── requirements.txt         # Python dependencies
│
├── assets/                  # Workflow screenshots for documentation
├── n8n/                     # Exported n8n workflow JSON files
│   ├── NBS Parse and Notify.json
│   └── NBS Scraper & Dispatch.json
│
├── samples/                 # Local storage for downloaded PDF reports
├── sql/                     # Database schemas (for Supabase/PostgreSQL)
├── src/                     # Python source code
│   ├── bot.py               # Telegram integration logic
│   ├── database.py          # Database operations
│   ├── parser.py            # Gemini AI extraction logic
│   ├── scraper.py           # NBS portal web scraper
│   └── utils/               # Helper modules (state mapping, prompts)
│
└── README.md
```

---

## ⚙️ Environment Configuration

Create a `.env` file in the root directory (alongside `docker-compose.yml`). You can copy the `.env.example` file:

```env
# Telegram Integration
TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrSTUvwxYZ"
TELEGRAM_CHAT_ID="987654321"

# Google Gemini API
GEMINI_API_KEY="AIzaSyA..."

# Database (Optional - for future Supabase integration)
SUPABASE_DB_URL="postgresql://user:password@host:port/dbname"
```

> **Note:** Ensure `.env` is included in your `.gitignore` to prevent accidental secret exposure.

---

## 🚀 Deployment & Installation

### 1. Start the n8n Container
Navigate to the project root and start the container:
```bash
docker compose up -d
```

### 2. Install Python Dependencies
The n8n container runs on Alpine Linux and includes Python 3.10. Because we are not using a custom `Dockerfile`, dependencies must be installed directly into the running container:

```bash
docker exec -it n8n_nbs_orchestrator pip3 install --no-cache-dir -r /data/requirements.txt
```
*(If `requirements.txt` is not mounted, run the `pip3 install` command explicitly with the required packages).*

### 3. Verify Installation
Ensure Python can successfully import all critical libraries:
```bash
docker exec -it n8n_nbs_orchestrator python3 -c "import requests, pdfplumber, google.genai, bs4, telegram; print('All systems go!')"
```

---

## 🧠 n8n Workflow Configuration

The system utilizes two distinct n8n workflows. You can import the JSON files located in the `/n8n` folder directly into your n8n instance.

### Workflow A: NBS Scraper & Dispatch
- **Trigger:** Monthly Schedule (or manual).
- **Logic:** Runs `scraper.py`. If the output contains `Downloaded 0 new files`, the workflow halts. Otherwise, it parses the JSON output, extracts the list of newly downloaded PDF paths, and passes them to Workflow B.
- **Crucial Setting:** The "Call 'NBS Parse and Notify'" node must be set to **Run once for each item** (n8n automatically loops through the PDFs).

### Workflow B: NBS Parse and Notify
- **Trigger:** Execute Sub-workflow Trigger (accepts `pdf_path`).
- **Logic:** Runs `parser.py --pdf-path "{{ $json.pdf_path }}"`, executes a custom JavaScript node to calculate national averages and top/bottom 3 states, and sends the result via the Telegram node.
- **Crucial Setting:** Telegram node must use **Parse Mode: HTML**.

---

## 🔧 Troubleshooting & Maintenance

### The "ModuleNotFoundError" Issue
Because dependencies are installed via `docker exec`, **destroying the container (`docker compose down`) will wipe the Python packages.** 
- *Fix:* You must re-run the `pip3 install` command from Step 2.
- *Long-term Fix:* Re-introduce a `Dockerfile` with a `RUN pip3 install` step to bake the packages into the image permanently.

### Handling Duplicate Files
The scraper includes a collision safety net. If you run the scraper manually multiple times, you may see files named `PMS Report MAY 2026_1.pdf`. 
- This is expected behavior to prevent data loss.
- The workflow will process *all* newly downloaded files. It is recommended to periodically prune the `samples/` folder on your host machine to keep it clean.

### Testing the Pipeline
To test the full pipeline without waiting for a new NBS report:
1. Delete the most recent PDF from the `samples/` folder.
2. Manually execute Workflow A in n8n.
3. Observe the execution logs in the n8n **Executions** tab and verify the Telegram message is received.

---
*Built for robust, automated data ingestion.*