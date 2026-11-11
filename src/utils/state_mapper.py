from rapidfuzz import process, fuzz

NIGERIAN_STATES = {
    "Abia": "South East", "Adamawa": "North East", "Akwa Ibom": "South South",
    "Anambra": "South East", "Bauchi": "North East", "Bayelsa": "South South",
    "Benue": "North Central", "Borno": "North East", "Cross River": "South South",
    "Delta": "South South", "Ebonyi": "South East", "Edo": "South South",
    "Ekiti": "South West", "Enugu": "South East", "FCT": "North Central",
    "Gombe": "North East", "Imo": "South East", "Jigawa": "North West",
    "Kaduna": "North West", "Kano": "North West", "Katsina": "North West",
    "Kebbi": "North West", "Kogi": "North Central", "Kwara": "North Central",
    "Lagos": "South West", "Nasarawa": "North Central", "Niger": "North Central",
    "Ogun": "South West", "Ondo": "South West", "Osun": "South West",
    "Oyo": "South West", "Plateau": "North Central", "Rivers": "South South",
    "Sokoto": "North West", "Taraba": "North East", "Yobe": "North East",
    "Zamfara": "North West"
}

def normalize_state(raw_name: str):
    clean_name = raw_name.replace("-", " ").strip()
    if clean_name.lower() in ["fct", "fct abuja", "abuja"]:
        return "FCT", "North Central"
        
    match, score, _ = process.extractOne(
        clean_name, 
        list(NIGERIAN_STATES.keys()), 
        scorer=fuzz.WRatio
    )
    if score >= 80:
        return match, NIGERIAN_STATES[match]
    return raw_name.title(), "Unknown"