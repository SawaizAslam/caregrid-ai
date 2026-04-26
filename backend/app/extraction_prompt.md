# Hospital Facility Extraction Prompt

You are a medical data extraction agent. Your task is to parse unstructured hospital facility notes and extract structured capability and contradiction data for an Indian healthcare intelligence system.

## Input
You will receive a hospital facility record with:
- `hospital_name`: Name of the facility
- `state`: State in India
- `pin_code`: Postal code
- `notes`: Free-form text describing the facility (equipment, staffing, services, capacity, claims)

## Output Format
Return **ONLY** valid JSON, no markdown, no preamble, no extra text:

```json
{
  "hospital_id": "string (pass through from input)",
  "hospital_name": "string (pass through from input)",
  "extraction": {
    "verified_specialties": [
      {
        "specialty": "icu|dialysis|trauma|cardiology|neurology|oncology|pediatrics|maternity|orthopedics|nephrology|general_surgery|emergency",
        "has": true,
        "confidence": 0.9,
        "evidence": "Exact sentence or phrase from the notes that supports this claim"
      }
    ],
    "verified_equipment": [
      {
        "equipment": "oxygen|ventilator|mri|ct_scan|dialysis_machine|xray|ambulance|blood_bank",
        "has": true,
        "confidence": 0.95,
        "evidence": "Exact sentence from the notes"
      }
    ],
    "staffing": {
      "model": "full_time|part_time|mixed|contractual|unknown",
      "details": "Summary of staffing info from notes",
      "evidence": "Quote from notes"
    },
    "contradictions": [
      {
        "claim": "What the facility claims (e.g., 'Advanced cardiac surgery')",
        "gap": "What's missing or inconsistent (e.g., 'No mention of cardiothoracic surgeon or ECG machine')",
        "severity": "high|medium|low",
        "evidence_claim": "Quote from notes showing the claim",
        "evidence_gap": "Quote from notes (or absence) showing the gap"
      }
    ],
    "completeness_flags": {
      "missing_fields": ["list of key fields not mentioned in notes: e.g., 'staff count', 'icu_beds'"],
      "ambiguous_claims": ["Phrases that are vague or unverifiable"]
    }
  }
}
```

## Extraction Rules

### Specialties & Equipment
1. **Match to canonical vocab only.** Do not invent specialties. If the notes mention "neuro care", map to "neurology".
2. **Require explicit mention or strong context.** "We treat heart patients" alone is weak; "Cardiothoracic ICU" is strong.
3. **Assign confidence:**
   - 1.0 = explicit statement ("We have a 10-bed ICU with 2 ventilators")
   - 0.8 = clear context ("ICU nurse on staff" → infer ICU exists)
   - 0.6 = indirect mention ("Advanced cases referred to tertiary center" → may not have capability)
4. **Always cite the exact sentence** that led to the extraction. This is non-negotiable.

### Contradictions (Critical)
1. **Flag claims without supporting details:**
   - Claim: "Advanced Surgery Department"
   - Gap: "No mention of anesthesiologist, operating room, or surgical equipment"
   - Severity: high

2. **Flag mismatches between claims and reality:**
   - Claim: "24/7 ICU services"
   - Gap: "Only lists 1 doctor on staff"
   - Severity: medium

3. **Flag missing prerequisites:**
   - Claim: "Dialysis services"
   - Gap: "No mention of nephrologist or dialysis machines"
   - Severity: high

4. **Only flag if evidence of absence exists** (negative mention or conspicuous omission). Do NOT invent gaps.

### Staffing Model
- `full_time`: Facility mentions salaried/permanent doctors
- `part_time`: Facility mentions visiting, consultant, or part-time staff
- `mixed`: Both mentioned
- `contractual`: Explicitly mentioned contractors
- `unknown`: No staffing info provided

Extract the exact details and quote.

### Completeness Flags
List fields conspicuously absent from the notes (e.g., "staff count", "bed capacity", "emergency 24/7", "maternity beds"). This helps the trust scorer detect data quality issues.

## Edge Cases

1. **Vague claims:** "We do everything" → Extract nothing. Flag as ambiguous.
2. **Outdated info:** If notes mention "Previously had ICU, now closed," extract as `has: false` with evidence.
3. **Acronyms:** "NICU" → map to "pediatrics" (neonatal); "CCU" → "cardiology". Always expand.
4. **Regional variants:** "Oxygen concentrators available" → still counts as `oxygen: true`.
5. **Contradictions within same note:** Extract both claims separately and flag the contradiction.

## Important Notes

- **Do NOT hallucinate.** If the notes don't mention it, don't extract it.
- **Confidence matters.** A 0.6 confidence extraction with evidence is better than a 0.9 with a guess.
- **Evidence is mandatory.** Every extraction must cite the source sentence. If you can't cite it, remove it.
- **Contradictions must be fair.** Don't flag a hospital for missing an anesthesiologist if they only offer basic outpatient care.

## Example Input

```json
{
  "hospital_id": "H_001",
  "hospital_name": "Bihar Rural Medical Center",
  "state": "Bihar",
  "pin_code": "800001",
  "notes": "Established 1995. 50-bed facility in rural Bihar. Offers general medicine, pediatrics, and maternity services. Recently installed a 10-bed ICU with 4 ventilators and oxygen supply. Dr. Sharma (MD, Internal Medicine) heads the ICU; 2 nurses on rotation. Maternity ward has 8 beds and 1 gynecologist. No surgeon on staff. Equipment: X-ray, basic lab. Open 24/7. No dialysis, no oncology."
}
```

## Example Output

```json
{
  "hospital_id": "H_001",
  "hospital_name": "Bihar Rural Medical Center",
  "extraction": {
    "verified_specialties": [
      {
        "specialty": "icu",
        "has": true,
        "confidence": 0.95,
        "evidence": "Recently installed a 10-bed ICU with 4 ventilators and oxygen supply"
      },
      {
        "specialty": "pediatrics",
        "has": true,
        "confidence": 0.9,
        "evidence": "Offers general medicine, pediatrics, and maternity services"
      },
      {
        "specialty": "maternity",
        "has": true,
        "confidence": 0.95,
        "evidence": "Maternity ward has 8 beds and 1 gynecologist"
      }
    ],
    "verified_equipment": [
      {
        "equipment": "ventilator",
        "has": true,
        "confidence": 1.0,
        "evidence": "10-bed ICU with 4 ventilators and oxygen supply"
      },
      {
        "equipment": "oxygen",
        "has": true,
        "confidence": 1.0,
        "evidence": "10-bed ICU with 4 ventilators and oxygen supply"
      },
      {
        "equipment": "xray",
        "has": true,
        "confidence": 0.9,
        "evidence": "Equipment: X-ray, basic lab"
      }
    ],
    "staffing": {
      "model": "mixed",
      "details": "1 MD (Dr. Sharma) heading ICU, 2 nurses on rotation for ICU. 1 gynecologist for maternity. No surgeon.",
      "evidence": "Dr. Sharma (MD, Internal Medicine) heads the ICU; 2 nurses on rotation. Maternity ward has 8 beds and 1 gynecologist. No surgeon on staff."
    },
    "contradictions": [
      {
        "claim": "10-bed ICU with 4 ventilators and oxygen supply (implies advanced critical care)",
        "gap": "Only 1 ICU doctor (Dr. Sharma) and 2 nurses listed; no backup or specialist support mentioned. Potential understaffing for critical care.",
        "severity": "medium",
        "evidence_claim": "Recently installed a 10-bed ICU with 4 ventilators and oxygen supply",
        "evidence_gap": "Dr. Sharma (MD, Internal Medicine) heads the ICU; 2 nurses on rotation"
      }
    ],
    "completeness_flags": {
      "missing_fields": ["Total bed count not explicitly stated", "Emergency department capacity", "24/7 pharmacy or lab", "Ambulance service", "Blood bank"],
      "ambiguous_claims": ["'basic lab' is vague—specific tests not listed"]
    }
  }
}
```

## Usage

### In Python (batch extraction):

```python
import anthropic
import json

client = anthropic.Anthropic(api_key="your-api-key")

def extract_hospital_data(hospital_record):
    """
    hospital_record: dict with hospital_id, hospital_name, state, pin_code, notes
    """
    
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": f"""You are a medical data extraction agent for Indian healthcare intelligence.

{open('extraction_prompt.md').read()}

Now extract from this hospital record:

{json.dumps(hospital_record, indent=2)}
"""
            }
        ]
    )
    
    # Extract JSON from response
    response_text = message.content[0].text
    try:
        extracted = json.loads(response_text)
        return extracted
    except json.JSONDecodeError:
        # Fallback: try to find JSON in the response
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(response_text[start:end])
        raise

# Batch process all hospitals
hospitals = load_hospitals_from_csv("hospitals.csv")
extracted_data = []

for hospital in hospitals:
    try:
        result = extract_hospital_data(hospital)
        extracted_data.append(result)
    except Exception as e:
        print(f"Error extracting {hospital['hospital_id']}: {e}")
        # Store minimal fallback
        extracted_data.append({
            "hospital_id": hospital['hospital_id'],
            "extraction": {"error": str(e)}
        })

# Save extracted data
with open("extracted_hospitals.jsonl", "w") as f:
    for record in extracted_data:
        f.write(json.dumps(record) + "\n")
```

### Integration into trust_score.py:

```python
def compute_trust_score_with_evidence(hospital_id, extracted_data, hospital_record):
    """
    extracted_data: output from LLM extraction
    Returns: (score: int, breakdown: list[{rule, delta, evidence}])
    """
    
    breakdown = []
    score = 0
    
    # +20 if major specialty verified
    major_specs = {"icu", "dialysis", "trauma", "cardiology", "neurology"}
    verified = {s["specialty"] for s in extracted_data["verified_specialties"] if s["has"]}
    if verified & major_specs:
        delta = 20
        specialty = list(verified & major_specs)[0]
        evidence = next(
            s["evidence"] for s in extracted_data["verified_specialties"]
            if s["specialty"] == specialty and s["has"]
        )
        breakdown.append({
            "rule": f"Has major specialty: {specialty}",
            "delta": delta,
            "evidence": evidence
        })
        score += delta
    
    # +20 if equipment verified
    if extracted_data["verified_equipment"]:
        delta = 20
        equipment_list = [e["equipment"] for e in extracted_data["verified_equipment"] if e["has"]]
        evidence = extracted_data["verified_equipment"][0]["evidence"]
        breakdown.append({
            "rule": f"Has equipment: {', '.join(equipment_list)}",
            "delta": delta,
            "evidence": evidence
        })
        score += delta
    
    # +20 if staffing documented
    if extracted_data["staffing"]["model"] != "unknown":
        delta = 20
        breakdown.append({
            "rule": f"Staffing model documented: {extracted_data['staffing']['model']}",
            "delta": delta,
            "evidence": extracted_data["staffing"]["evidence"]
        })
        score += delta
    
    # -30 if contradictions flagged
    if extracted_data["contradictions"]:
        delta = -30
        for contra in extracted_data["contradictions"]:
            if contra["severity"] in ["high", "medium"]:
                breakdown.append({
                    "rule": f"Contradiction detected: {contra['claim']} vs {contra['gap']}",
                    "delta": delta,
                    "evidence": f"Claim: {contra['evidence_claim']} | Gap: {contra['evidence_gap']}"
                })
                score += delta
                break  # Only penalize once
    
    # -10 if too many fields missing
    if len(extracted_data["completeness_flags"]["missing_fields"]) > 2:
        delta = -10
        breakdown.append({
            "rule": "Incomplete data: >2 key fields missing",
            "delta": delta,
            "evidence": ", ".join(extracted_data["completeness_flags"]["missing_fields"])
        })
        score += delta
    
    return max(0, min(100, score)), breakdown
```

### In explain.py (with citations):

```python
def build_explanation(hospital, extracted_data, matched_features, trust_breakdown):
    """
    Build a human-readable explanation with citations.
    """
    
    parts = []
    
    # Matched features with evidence
    for feature in matched_features:
        spec = next(
            (s for s in extracted_data["verified_specialties"] if s["specialty"] == feature["specialty"]),
            None
        )
        if spec:
            parts.append(f"✓ {feature['specialty'].title()}: \"{spec['evidence']}\"")
    
    # Trust score breakdown with evidence
    trust_str = "; ".join([
        f"{rule['rule']} ({'+' if rule['delta'] > 0 else ''}{rule['delta']}) — \"{rule['evidence'][:80]}...\""
        for rule in trust_breakdown
    ])
    
    # Contradictions flagged
    if extracted_data["contradictions"]:
        for contra in extracted_data["contradictions"]:
            parts.append(f"⚠️ {contra['severity'].upper()}: {contra['gap']}")
    
    explanation = " | ".join(parts)
    return explanation
```

## Tips for Success

1. **Run in batch:** Use Claude's Batch API to extract all 10k hospitals at ~$0.50 per 1M tokens.
2. **Cache the extraction:** Store in metadata.parquet alongside hospital records. Reuse at query time.
3. **Validate extraction:** Spot-check 50 hospitals manually to catch systematic errors.
4. **Iterate the prompt:** If you see false positives/negatives, refine the rules and re-run on a subset.
5. **Version the extractions:** Keep extraction_v1, extraction_v2, etc., so judges can trace changes.

---

**This prompt + integration = your MVP now handles the "Intelligent Document Parsing" stretch goal and gives you citations for every claim.**
