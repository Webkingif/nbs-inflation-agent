import os
import json
import pdfplumber
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional
from utils.state_mapper import normalize_state

# Initialize the Gemini client (picks up GEMINI_API_KEY from environment variables)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class StatePriceItem(BaseModel):
    raw_state_name: str = Field(description="State name extracted from table")
    item_category: str = Field(description="Category e.g. PMS Retail, Bus Intercity, Okada")
    price_ngn: float = Field(description="Numerical price value in Naira")
    mom_change_pct: Optional[float] = Field(None, description="Month on month percentage change")
    yoy_change_pct: Optional[float] = Field(None, description="Year on year percentage change")

class NBSParsedPayload(BaseModel):
    publication_month: int
    publication_year: int
    report_type: str
    data_records: List[StatePriceItem]

def extract_pdf_content(pdf_path: str) -> str:
    raw_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for idx, page in enumerate(pdf.pages[2:10]):
            text = page.extract_text()
            tables = page.extract_tables()
            if text:
                raw_text += f"\n--- PAGE {idx + 3} TEXT ---\n" + text
            if tables:
                raw_text += f"\n--- PAGE {idx + 3} TABLES ---\n" + json.dumps(tables)
    return raw_text

def parse_nbs_pdf(pdf_path: str) -> NBSParsedPayload:
    document_content = extract_pdf_content(pdf_path)
    
    system_prompt = """
    You are an expert data parsing assistant specializing in Nigerian National Bureau of Statistics (NBS) reports.
    Extract state-by-state price data for all 36 states and the FCT.
    Extract only numbers for prices and percentage changes.
    """
    
    # Call Gemini with structured output configuration
    response = client.models.generate_content(
        model="gemini-2.5-flash",  # You can also use "gemini-2.5-pro" for heavier tasks
        contents=f"Extract structured metrics from this text:\n{document_content[:14000]}",
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=NBSParsedPayload,
            temperature=0.0,
        ),
    )
    
    # Gemini automatically parses the response into your Pydantic model
    parsed: NBSParsedPayload = response.parsed
    
    for record in parsed.data_records:
        std_state, zone = normalize_state(record.raw_state_name)
        record.raw_state_name = std_state
        
    return parsed