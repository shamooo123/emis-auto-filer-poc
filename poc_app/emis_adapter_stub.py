import uuid
from datetime import datetime

def fetch_new_results():
    """
    Simulates fetching unfiled pathology results from EMIS.
    Returns a list of dictionaries mapped to the clinical engine's expected data shape[cite: 23].
    """
    return [
        # CASE 1: The Perfect Auto-File (Vitamin D)
        # Should pass: Normal lab flag, value > 50, no interfering meds[cite: 83, 84].
        {
            "id": str(uuid.uuid4()),
            "patient_id": "NHS-111-222-3333",
            "age": 45,
            "sex": "F",
            "test_type": "Vitamin D (25-OH)",
            "value": 65.0,
            "units": "nmol/L",
            "lab_normal_flag": True,
            "prior_result": 58.0,
            "active_medications": ["Paracetamol"],
            "coded_conditions": ["Asthma"]
        },
        
        # CASE 2: The Context Block (TSH)
        # Should fail/route: Value is in range (0.27 - 4.20) [cite: 86], BUT patient is on Levothyroxine[cite: 87].
        {
            "id": str(uuid.uuid4()),
            "patient_id": "NHS-444-555-6666",
            "age": 62,
            "sex": "F",
            "test_type": "TSH",
            "value": 2.1,
            "units": "mIU/L",
            "lab_normal_flag": True,
            "prior_result": 2.5,
            "active_medications": ["Levothyroxine", "Amlodipine"],
            "coded_conditions": ["Hypothyroidism"]
        },

        # CASE 3: The Range Block (HbA1c)
        # Should fail/route: Lab might not flag 45 as strictly 'abnormal', but it hits the pre-diabetes threshold (≥ 42)[cite: 91].
        {
            "id": str(uuid.uuid4()),
            "patient_id": "NHS-777-888-9999",
            "age": 50,
            "sex": "M",
            "test_type": "HbA1c",
            "value": 45.0,
            "units": "mmol/mol",
            "lab_normal_flag": True,
            "prior_result": 40.0,
            "active_medications": [],
            "coded_conditions": []
        },

        # CASE 4: The Delta Block (U&E / eGFR)
        # Should fail/route: Value is > 60 [cite: 101], but has dropped sharply from 90 to 65 (adverse delta)[cite: 102].
        {
            "id": str(uuid.uuid4()),
            "patient_id": "NHS-000-111-2222",
            "age": 71,
            "sex": "M",
            "test_type": "eGFR",
            "value": 65.0,
            "units": "mL/min",
            "lab_normal_flag": True, # Lab might say 65 is technically normal
            "prior_result": 90.0,    # But the engine must catch this 27% drop
            "active_medications": ["Ramipril"],
            "coded_conditions": ["Hypertension"]
        },
        
        # CASE 5: The Primary Gate Block (Lab Flag)
        # Should fail/route: Fails the primary safety rule because the lab flagged it[cite: 68].
        {
            "id": str(uuid.uuid4()),
            "patient_id": "NHS-333-444-5555",
            "age": 28,
            "sex": "M",
            "test_type": "Vitamin D (25-OH)",
            "value": 20.0,
            "units": "nmol/L",
            "lab_normal_flag": False, # Lab flagged as abnormal/low
            "prior_result": None,     # No baseline [cite: 79]
            "active_medications": [],
            "coded_conditions": []
        }
    ]

def file_result(result_id: str, status: str, comment: str):
    """
    LIVE ONLY: Sets the filing status and inserts a coded comment[cite: 23].
    In our shadow mode PoC, this simply prints to the console/logger to prove the seam works.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # In the live EMIS environment, this would execute RPA clicks or hit the Partner API.
    print(f"[{timestamp}] MOCK EMIS API CALL -> Filed {result_id} | Status: {status} | Comment: {comment}")
    return True