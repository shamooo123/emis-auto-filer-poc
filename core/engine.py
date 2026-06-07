import json
import os

class ClinicalDecisionEngine:
    def __init__(self, rules_path="core/rules.json"):
        with open(rules_path, "r") as f:
            self.rules = {rule["test"]: rule for rule in json.load(f)}

    def evaluate(self, result: dict) -> tuple[str, list[str]]:
        """
        Evaluates a single result against universal safety nets and specific test configurations.
        Returns (Decision, Reasons List)
        """
        reasons = []
        test_type = result.get("test_type")

        # 1. Universal Safety Net: Completeness Check[cite: 2]
        required_fields = ["id", "patient_id", "age", "sex", "test_type", "value", "lab_normal_flag"]
        for field in required_fields:
            if result.get(field) is None:
                return "Route to Human", ["Completeness Check Failed: Missing field: " + field]

        # Check if the test is supported in our configuration[cite: 1]
        if test_type not in self.rules:
            return "Route to Human", [f"Unsupported or deferred test type: {test_type}"]

        config = self.rules[test_type]

        # 2. Universal Safety Net: Primary Gate (Lab Flag)[cite: 2]
        if config["require_lab_normal_flag"] and not result["lab_normal_flag"]:
            reasons.append("Primary Gate Block: Laboratory flagged result as abnormal")[cite: 2]

        # 3. Universal Safety Net: Baseline Check (Prior Result)[cite: 2]
        if config["require_prior_result"] and result.get("prior_result") is None:
            reasons.append("Baseline Check Failed: No prior result available for trend comparison")[cite: 2]

        # 4. Numeric Range Check (Tier A Ranges)[cite: 2]
        for param in config["params"]:
            if param["sex"] != "any" and param["sex"] != result["sex"]:
                continue
            if not (param["low"] <= result["value"] <= param["high"]):
                reasons.append(f"Range Block: Value {result['value']} {result['units']} outside Tier A range ({param['low']}-{param['high']})")[cite: 2]

        # 5. Delta / Trend Check[cite: 2]
        if config["delta"]["enabled"] and result.get("prior_result") is not None:
            prior = result["prior_result"]
            current = result["value"]
            max_pct = config["delta"]["max_adverse_pct"]
            
            # Calculate percentage change
            if prior > 0:
                pct_change = abs(current - prior) / prior * 100
                # Specific adverse logic can be customized per test; here we flag a generic high variance drop/jump[cite: 2]
                if pct_change > max_pct:
                    reasons.append(f"Delta Block: Significant shift of {pct_change:.1f}% vs prior result ({prior}) exceeds safe threshold ({max_pct}%)")[cite: 2]

        # 6. Medication & Condition Context Blocks[cite: 2]
        for active_med in result.get("active_medications", []):
            if active_med in config["med_context_block"]:
                reasons.append(f"Context Block: Active repeat medication tracking requires human review ({active_med})")[cite: 2]

        for condition in result.get("coded_conditions", []):
            if condition in config["condition_context_block"]:
                reasons.append(f"Context Block: Active coded condition alters standard interpretation ({condition})")[cite: 2]

        # Final Evaluation Gate
        if reasons:
            return "Route to Human", reasons
        
        return "Auto-file (Tier A)", ["All clinical gates passed successfully"][cite: 2]