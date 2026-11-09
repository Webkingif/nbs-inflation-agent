-- 1. Report Metadata Trackers
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_type VARCHAR(50) NOT NULL, -- 'PMS', 'DIESEL', 'TRANSPORT'
    publication_month INT NOT NULL CHECK (publication_month BETWEEN 1 AND 12),
    publication_year INT NOT NULL CHECK (publication_year >= 2020),
    source_url TEXT UNIQUE NOT NULL,
    file_name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_report_period UNIQUE (report_type, publication_month, publication_year)
);

-- 2. State Level Pricing Table
CREATE TABLE IF NOT EXISTS state_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID REFERENCES reports(id) ON DELETE CASCADE,
    state_name VARCHAR(50) NOT NULL,
    geopolitical_zone VARCHAR(20) CHECK (geopolitical_zone IN ('North Central', 'North East', 'North West', 'South East', 'South South', 'South West')),
    item_category VARCHAR(100) NOT NULL, -- e.g. "PMS Retail Price", "Bus Journey Within City", "Okada Fare"
    price_ngn NUMERIC(10, 2) NOT NULL,
    mom_change_pct NUMERIC(6, 2),
    yoy_change_pct NUMERIC(6, 2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Indexes for fast Text-to-SQL Querying
CREATE INDEX IF NOT EXISTS idx_state_lookup ON state_prices(state_name, item_category);
CREATE INDEX IF NOT EXISTS idx_report_dates ON reports(publication_year, publication_month);

-- 4. Analytical View: Month-on-Month State Variance Comparison
CREATE OR REPLACE VIEW view_state_price_variances AS
SELECT 
    sp.state_name,
    sp.geopolitical_zone,
    sp.item_category,
    sp.price_ngn,
    sp.mom_change_pct,
    sp.yoy_change_pct,
    r.publication_month,
    r.publication_year
FROM state_prices sp
JOIN reports r ON sp.report_id = r.id;