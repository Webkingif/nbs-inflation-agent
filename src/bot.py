import os
import psycopg2
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("SUPABASE_DB_URL")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Initialize the Gemini client (picks up GEMINI_API_KEY from environment variables)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

TEXT_TO_SQL_PROMPT = """
You are a PostgreSQL data engineer bot for Nigerian fuel & transport statistics.
Database Schema:
1. reports (id, report_type, publication_month, publication_year)
2. state_prices (id, report_id, state_name, geopolitical_zone, item_category, price_ngn, mom_change_pct, yoy_change_pct)
3. View: view_state_price_variances (state_name, geopolitical_zone, item_category, price_ngn, mom_change_pct, publication_month, publication_year)

Generate ONLY valid PostgreSQL SQL statements in response to user questions. No markdown formatting, no explanations.

Example Input: What was the diesel price variance between Lagos and Abuja in the latest report?
Example Output:
SELECT state_name, item_category, price_ngn, publication_month, publication_year 
FROM view_state_price_variances 
WHERE state_name IN ('Lagos', 'FCT') AND item_category ILIKE '%diesel%'
ORDER BY publication_year DESC, publication_month DESC LIMIT 2;
"""

def run_query(sql_query: str):
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute(sql_query)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    conn.close()
    return columns, rows

def format_answer(user_question: str, cols: list, rows: list) -> str:
    prompt = f"""
    User Question: {user_question}
    SQL Result Header: {cols}
    SQL Result Rows: {rows}
    
    Summarize the data into a helpful response for a logistics manager. State key price differences in NGN.
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text

async def handle_user_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_prompt = update.message.text
    await update.message.reply_text("🔎 Querying NBS database...")
    
    try:
        # Generate SQL using Gemini with system instructions
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=TEXT_TO_SQL_PROMPT,
                temperature=0.0
            ),
        )
        
        # Clean up response text in case markdown blocks were included
        sql = response.text.strip().replace("```sql", "").replace("```", "").strip()
        
        cols, rows = run_query(sql)
        reply = format_answer(user_prompt, cols, rows)
        await update.message.reply_text(reply)
        
    except Exception as err:
        await update.message.reply_text(f"⚠️ Error fulfilling query: {str(err)}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_user_query))
    print("🤖 Telegram Bot Running locally...")
    app.run_polling()