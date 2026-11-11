import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("SUPABASE_DB_URL")

def get_db_connection():
    return psycopg2.connect(DB_URL)

def insert_report_metadata(report_type: str, month: int, year: int, source_url: str, file_name: str) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        INSERT INTO reports (report_type, publication_month, publication_year, source_url, file_name)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (report_type, publication_month, publication_year) DO UPDATE 
        SET created_at = NOW()
        RETURNING id;
    """
    cursor.execute(query, (report_type, month, year, source_url, file_name))
    report_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return report_id

def insert_state_prices(report_id: str, records: list):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        INSERT INTO state_prices (report_id, state_name, geopolitical_zone, item_category, price_ngn, mom_change_pct, yoy_change_pct)
        VALUES (%s, %s, %s, %s, %s, %s, %s);
    """
    for r in records:
        cursor.execute(query, (
            report_id, r['state_name'], r['geopolitical_zone'], 
            r['item_category'], r['price_ngn'], r['mom_change_pct'], r['yoy_change_pct']
        ))
    conn.commit()
    conn.close()