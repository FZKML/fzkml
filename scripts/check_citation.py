"""Validate the JSON-formatted YAML citation against the pinned official schema."""
import json
from pathlib import Path
from jsonschema import Draft7Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
schema = json.loads((ROOT / "compliance/cff-schema.json").read_text())
citation = json.loads((ROOT / "CITATION.cff").read_text())
Draft7Validator.check_schema(schema)
Draft7Validator(schema, format_checker=FormatChecker()).validate(citation)
if ("version" in citation) != ("date-released" in citation):
    raise ValueError("release version and date-released must be updated together")
print("CITATION.cff passes official CFF 1.2.0 schema validation")
