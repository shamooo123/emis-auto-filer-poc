from datetime import datetime

def fetch_new_results():
    """
    Simulate fetching unfiled blood results from EMIS.
    Uses pseudonymous patient identifiers only for local PoC testing.
    """
    return [
        {
            "id": "RES-VITD-001",
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
        {
            "id": "RES-TSH-001",
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
        {
            "id": "RES-HBA1C-001",
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
        {
            "id": "RES-EGFR-001",
            "patient_id": "NHS-000-111-2222",
            "age": 71,
            "sex": "M",
            "test_type": "eGFR",
            "value": 65.0,
            "units": "mL/min",
            "lab_normal_flag": True,
            "prior_result": 90.0,
            "active_medications": ["Ramipril"],
            "coded_conditions": ["Hypertension"]
        },
        {
            "id": "RES-VITD-002",
            "patient_id": "NHS-333-444-5555",
            "age": 28,
            "sex": "M",
            "test_type": "Vitamin D (25-OH)",
            "value": 20.0,
            "units": "nmol/L",
            "lab_normal_flag": False,
            "prior_result": None,
            "active_medications": [],
            "coded_conditions": []
        },
        {
            "id": "RES-FERRITIN-001",
            "patient_id": "NHS-555-666-7777",
            "age": 39,
            "sex": "F",
            "test_type": "Ferritin",
            "value": 35.0,
            "units": "ug/L",
            "lab_normal_flag": True,
            "prior_result": 36.0,
            "active_medications": [],
            "coded_conditions": []
        }
    ]

def file_result(result_id: str, status: str, comment: str):
    """
    LIVE ONLY seam:
    In production this would call EMIS/partner API or RPA workflow.
    For the PoC we only emit a local log message.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] MOCK EMIS API CALL -> Filed {result_id} | Status: {status} | Comment: {comment}")
    return True