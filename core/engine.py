import json
from pathlib import Path


class ClinicalDecisionEngine:
    def __init__(self, rules_path: str | None = None):
        base_dir = Path(__file__).resolve().parent
        resolved_rules_path = Path(rules_path) if rules_path else base_dir / "rules.json"
        with resolved_rules_path.open("r", encoding="utf-8") as rules_file:
            self.rules = {rule["test"]: rule for rule in json.load(rules_file)}

    def evaluate(self, result: dict) -> tuple[str, list[str]]:
        """
        Evaluate one blood result against universal safety nets + per-test rules.
        Returns (decision, reasons).
        """
        reasons: list[str] = []
        test_type = result.get("test_type")

        required_fields = [
            "id",
            "patient_id",
            "age",
            "sex",
            "test_type",
            "value",
            "units",
            "lab_normal_flag",
        ]
        for field in required_fields:
            if result.get(field) is None:
                return "Route to Human", [f"Completeness Check Failed: missing '{field}'"]

        if test_type not in self.rules:
            return "Route to Human", [f"Unsupported or deferred test type: {test_type}"]

        config = self.rules[test_type]

        if config.get("require_lab_normal_flag", True) and not result["lab_normal_flag"]:
            reasons.append("Primary Gate Block: laboratory flagged result as abnormal")

        if config.get("require_prior_result", False) and result.get("prior_result") is None:
            reasons.append("Baseline Check Failed: no prior result available for trend comparison")

        sex = str(result["sex"]).lower()
        value = float(result["value"])
        matching_ranges = [
            param
            for param in config.get("params", [])
            if str(param.get("sex", "any")).lower() in ("any", sex)
        ]
        if not matching_ranges:
            reasons.append(f"No range config available for sex '{result['sex']}'")
        else:
            for param in matching_ranges:
                low = float(param["low"])
                high = float(param["high"])
                if not (low <= value <= high):
                    reasons.append(
                        "Range Block: "
                        f"value {value} {result['units']} outside Tier A range ({low}-{high})"
                    )

        delta_cfg = config.get("delta", {})
        prior = result.get("prior_result")
        if delta_cfg.get("enabled") and prior is not None:
            prior_value = float(prior)
            if prior_value > 0:
                pct_change = abs(value - prior_value) / prior_value * 100
                max_pct = float(delta_cfg.get("max_adverse_pct", 999))
                if pct_change > max_pct:
                    reasons.append(
                        "Delta Block: "
                        f"significant shift of {pct_change:.1f}% vs prior result ({prior_value}) "
                        f"exceeds safe threshold ({max_pct}%)"
                    )

        med_context_block = {med.lower() for med in config.get("med_context_block", [])}
        for active_med in result.get("active_medications", []):
            if str(active_med).lower() in med_context_block:
                reasons.append(
                    f"Context Block: active repeat medication requires clinician review ({active_med})"
                )

        condition_context_block = {
            condition.lower() for condition in config.get("condition_context_block", [])
        }
        for condition in result.get("coded_conditions", []):
            if str(condition).lower() in condition_context_block:
                reasons.append(
                    f"Context Block: coded condition changes interpretation ({condition})"
                )

        if reasons:
            return "Route to Human", reasons

        return "Auto-file (Tier A)", ["All clinical gates passed successfully"]