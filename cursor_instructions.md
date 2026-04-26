# Cursor Instructions: Add LLM-Powered Extraction to HackNation Backend

## Objective
Integrate Claude-based intelligent document parsing into the existing FastAPI backend to extract capabilities, staffing, and contradictions from unstructured hospital notes with full citation support.

## What We're Building
Add a new module `backend/app/extraction.py` that:
1. Extracts verified specialties, equipment, staffing, and contradictions from hospital notes using Claude API
2. Caches extracted data in metadata.parquet
3. Integrates with existing trust_score.py to cite evidence for every score rule
4. Modifies explain.py to show "Matched: ICU (evidence: '10-bed ICU with 4 ventilators')"
5. Updates requirements.txt with anthropic SDK

## Files to Create/Modify

### 1. Create: `backend/app/extraction.py`

This is the core LLM extraction module. Should:

**Imports:**
- anthropic
- json
- pandas
- logging
- retry decorator (for resilience)

**Class: `HospitalExtractor`**
- `__init__(api_key: str, model: str = "claude-3-5-sonnet-20241022")`
- `extract_single(hospital_record: dict) -> dict` — Calls Claude API with the extraction prompt, returns JSON
- `extract_batch(hospitals_df: pd.DataFrame) -> pd.DataFrame` — Maps extract_single over all rows, handles errors gracefully
- `load_prompt(prompt_path: str) -> str` — Reads the extraction_prompt.md file

**Key details:**
- Each API call should use max_tokens=2000
- Parse response as JSON; handle malformed responses with try/except
- On error: log and return minimal {"hospital_id": id, "extraction": {"error": "..."}}
- Add exponential backoff retry (3 attempts) for transient failures
- Track API costs if possible (log tokens used)

**Integration point:** Should be called once at startup in `main.py` during lifespan, or as a separate CLI script `scripts/extract_hospitals.py`

### 2. Modify: `backend/app/trust_score.py`

Update `compute_trust_score(hospital: dict) -> tuple[int, list]` to accept extracted data.

**New signature:**
```python
def compute_trust_score(hospital: dict, extracted_data: dict = None) -> tuple[int, list[dict]]:
    """
    hospital: original hospital record
    extracted_data: output from HospitalExtractor (has .verified_specialties, .verified_equipment, .contradictions, etc.)
    
    Returns: (score: int, breakdown: list[{rule, delta, evidence}])
    """
```

**Logic (provided in the extraction prompt, but implement here):**
- +20 if any major specialty (ICU/dialysis/trauma/cardiology/neurology) in extracted_data["verified_specialties"] with has=true
  - Append to breakdown with rule, delta, **evidence**: the exact quote from the hospital notes
- +20 if verified_equipment is non-empty
  - Evidence: list of equipment found
- +20 if staffing model != "unknown"
  - Evidence: the staffing.evidence field from extraction
- -30 if contradictions exist with severity in ["high", "medium"]
  - Evidence: "Claim: X | Gap: Y"
- -10 if >2 completeness_flags.missing_fields
  - Evidence: list of missing fields

**Important:** Each breakdown item must have a `evidence` field (string). This is what appears in explain.py.

**Backward compatibility:** If extracted_data is None, fall back to current keyword-based logic (for hospitals without extraction yet).

### 3. Modify: `backend/app/explain.py`

Update `build_explanation(hospital, matched_features, trust_breakdown, trust_score) -> str` to show citations.

**New logic:**
```python
def build_explanation(hospital, matched_features, trust_breakdown, trust_score, extracted_data=None):
    """
    Build explanation with citations from extracted data.
    """
    parts = []
    
    # Matched specialties with evidence
    if extracted_data:
        for spec in extracted_data.get("verified_specialties", []):
            if spec["has"] and spec["specialty"] in [f["specialty"] for f in matched_features]:
                parts.append(f"✓ {spec['specialty'].title()}: \"{spec['evidence'][:100]}\"")
    else:
        parts.append(f"✓ Matched: {', '.join([f['specialty'] for f in matched_features])}")
    
    # Trust breakdown with citations
    if trust_breakdown:
        for item in trust_breakdown:
            delta_str = f"+{item['delta']}" if item['delta'] > 0 else str(item['delta'])
            evidence_snippet = item.get('evidence', '')[:80]
            parts.append(f"{item['rule']} ({delta_str}) — \"{evidence_snippet}...\"")
    
    # Contradictions
    if extracted_data:
        for contra in extracted_data.get("contradictions", []):
            if contra.get("severity") in ["high", "medium"]:
                parts.append(f"⚠️ {contra['severity'].upper()}: {contra['gap']}")
    
    explanation = " | ".join(parts)
    return explanation
```

### 4. Modify: `backend/app/data_loader.py`

Add a function to load extracted data from a persisted file:

```python
def load_extracted_data(extracted_path: str) -> dict[str, dict]:
    """
    Load extracted hospital data from JSONL or parquet.
    Returns: {hospital_id: extracted_record}
    """
    if extracted_path.endswith('.jsonl'):
        extracted = {}
        with open(extracted_path, 'r') as f:
            for line in f:
                record = json.loads(line)
                extracted[record['hospital_id']] = record['extraction']
        return extracted
    elif extracted_path.endswith('.parquet'):
        df = pd.read_parquet(extracted_path)
        return dict(zip(df['hospital_id'], df['extraction']))
    else:
        raise ValueError("extracted_path must be .jsonl or .parquet")
```

Integrate into lifespan so extracted data is loaded at startup.

### 5. Modify: `backend/app/main.py`

Update the lifespan context manager to call extraction:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Loading dataset...")
    df = load_hospitals_from_csv(config.HOSPITALS_CSV_PATH)
    
    logger.info("Loading or building indices...")
    embeddings = EmbeddingsIndex(config.FAISS_INDEX_PATH)
    embeddings.load_or_build(df)
    
    # NEW: Load extracted data or build it
    logger.info("Loading extracted hospital data...")
    if os.path.exists(config.EXTRACTED_DATA_PATH):
        extracted_dict = load_extracted_data(config.EXTRACTED_DATA_PATH)
        logger.info(f"Loaded extracted data for {len(extracted_dict)} hospitals")
    else:
        logger.warning("Extracted data not found. Run: python scripts/extract_hospitals.py")
        extracted_dict = {}
    
    # Store in app state
    app.state.df = df
    app.state.embeddings = embeddings
    app.state.extracted_dict = extracted_dict  # NEW
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
```

### 6. Modify: `backend/app/search.py`

Update `search_and_rank()` to pass extracted data to trust_score and explain:

```python
def search_and_rank(query_str, df, embeddings, extracted_dict, trust_scores_cache):
    """
    ... existing logic ...
    """
    
    # For each candidate hospital
    results = []
    for hospital_id in top_candidate_ids:
        hospital = df.loc[hospital_id]
        
        # Get extracted data (or None if not available)
        extracted = extracted_dict.get(hospital_id, None)
        
        # Compute trust score with extracted data
        trust_score, trust_breakdown = compute_trust_score(hospital, extracted)
        
        # Build matched features
        matched_features = get_matched_features(query, hospital, extracted)
        
        # Build explanation with citations
        explanation = build_explanation(hospital, matched_features, trust_breakdown, trust_score, extracted)
        
        results.append({
            "hospital_id": hospital_id,
            "name": hospital["hospital_name"],
            "state": hospital["state"],
            "pin": hospital["pin_code"],
            "matched_features": matched_features,
            "trust_score": trust_score,
            "trust_breakdown": trust_breakdown,  # Include full breakdown with evidence
            "explanation": explanation,
            "extracted_data": extracted,  # Optional: include for debugging
            ...
        })
    
    return results
```

### 7. Create: `backend/scripts/extract_hospitals.py`

Standalone CLI script to extract all hospitals and persist results:

```python
#!/usr/bin/env python
"""
One-shot CLI to extract hospital data using Claude API.
Usage: python scripts/extract_hospitals.py --input data/hospitals.csv --output data/extracted_hospitals.jsonl
"""

import argparse
import json
import logging
from pathlib import Path
from app.data_loader import load_hospitals_from_csv
from app.extraction import HospitalExtractor
from app.config import Config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/hospitals.csv", help="Hospital CSV path")
    parser.add_argument("--output", default="data/extracted_hospitals.jsonl", help="Output JSONL path")
    parser.add_argument("--api-key", default=None, help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    parser.add_argument("--sample", type=int, default=None, help="Test on first N hospitals only")
    args = parser.parse_args()
    
    # Load hospitals
    logger.info(f"Loading hospitals from {args.input}")
    df = load_hospitals_from_csv(args.input)
    if args.sample:
        df = df.head(args.sample)
        logger.info(f"Using sample of {len(df)} hospitals for testing")
    
    # Initialize extractor
    logger.info("Initializing HospitalExtractor")
    extractor = HospitalExtractor(api_key=args.api_key)
    
    # Extract all
    logger.info(f"Extracting data from {len(df)} hospitals...")
    extracted_results = extractor.extract_batch(df)
    
    # Save
    logger.info(f"Saving to {args.output}")
    extracted_results.to_json(args.output, orient='records', lines=True)
    logger.info(f"Done! Extracted data saved to {args.output}")

if __name__ == "__main__":
    main()
```

### 8. Modify: `backend/requirements.txt`

Add:
```
anthropic>=0.7.0
```

### 9. Modify: `backend/app/config.py`

Add new config vars:

```python
EXTRACTED_DATA_PATH = os.getenv("EXTRACTED_DATA_PATH", "data/extracted_hospitals.jsonl")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
EXTRACTION_PROMPT_PATH = os.getenv("EXTRACTION_PROMPT_PATH", "app/extraction_prompt.md")
```

### 10. Copy: `backend/app/extraction_prompt.md`

Copy the extraction_prompt.md file provided earlier into `backend/app/extraction_prompt.md`. This is the system prompt used by Claude.

---

## Implementation Checklist

- [ ] **Create extraction.py** with HospitalExtractor class
  - [ ] extract_single() method with Claude API call
  - [ ] extract_batch() method with retry logic
  - [ ] Error handling and logging
  - [ ] JSON parsing with fallback

- [ ] **Update trust_score.py**
  - [ ] Accept extracted_data parameter
  - [ ] Refactor logic to pull evidence from extracted_data
  - [ ] Maintain backward compatibility (extracted_data=None)
  - [ ] Ensure each breakdown item has .evidence field

- [ ] **Update explain.py**
  - [ ] Accept extracted_data parameter
  - [ ] Build explanation with citations from extracted data
  - [ ] Handle None case gracefully

- [ ] **Update data_loader.py**
  - [ ] Add load_extracted_data() function
  - [ ] Support .jsonl and .parquet formats

- [ ] **Update main.py lifespan**
  - [ ] Load extracted data at startup
  - [ ] Store in app.state
  - [ ] Handle missing extracted data gracefully

- [ ] **Update search.py**
  - [ ] Pass extracted_dict to search functions
  - [ ] Update compute_trust_score call signature
  - [ ] Update explain call signature
  - [ ] Include trust_breakdown in response

- [ ] **Create extract_hospitals.py CLI**
  - [ ] Argument parsing
  - [ ] Batch extraction logic
  - [ ] Progress logging
  - [ ] Error recovery

- [ ] **Update requirements.txt**
  - [ ] Add anthropic SDK

- [ ] **Update config.py**
  - [ ] Add EXTRACTED_DATA_PATH, ANTHROPIC_API_KEY, EXTRACTION_PROMPT_PATH

- [ ] **Copy extraction_prompt.md**
  - [ ] Place in backend/app/extraction_prompt.md

- [ ] **Test**
  - [ ] Run extract_hospitals.py on 5 sample hospitals
  - [ ] Verify extracted JSON structure
  - [ ] Test trust_score with extracted data
  - [ ] Test explain output with citations
  - [ ] Test /search endpoint returns trust_breakdown

---

## Testing Strategy

### Unit Tests to Add

**test_extraction.py:**
```python
def test_extract_single():
    """Test extraction on a sample hospital record"""
    extractor = HospitalExtractor(api_key="...")
    hospital = {"hospital_id": "H_001", "notes": "10-bed ICU with ventilators..."}
    result = extractor.extract_single(hospital)
    assert result["hospital_id"] == "H_001"
    assert "extraction" in result
    assert any(s["specialty"] == "icu" for s in result["extraction"]["verified_specialties"])

def test_extract_batch():
    """Test batch extraction"""
    df = load_hospitals_from_csv("data/hospitals.csv").head(5)
    extractor = HospitalExtractor(api_key="...")
    results = extractor.extract_batch(df)
    assert len(results) == 5
    assert all("extraction" in row for _, row in results.iterrows())
```

**test_trust_score_with_extraction.py:**
```python
def test_trust_score_with_extracted_data():
    """Test trust_score uses extracted data for evidence"""
    hospital = {"hospital_id": "H_001"}
    extracted = {
        "verified_specialties": [{"specialty": "icu", "has": True, "evidence": "10-bed ICU"}],
        "verified_equipment": [],
        "contradictions": []
    }
    score, breakdown = compute_trust_score(hospital, extracted)
    assert score >= 20
    assert any(b["evidence"] == "10-bed ICU" for b in breakdown)
```

**test_explain_with_citations.py:**
```python
def test_explain_includes_citations():
    """Test explanation includes extracted evidence"""
    hospital = {"hospital_id": "H_001"}
    extracted = {"verified_specialties": [{"specialty": "icu", "has": True, "evidence": "10-bed ICU"}]}
    breakdown = [{"rule": "Has ICU", "delta": 20, "evidence": "10-bed ICU"}]
    explanation = build_explanation(hospital, [], breakdown, 50, extracted)
    assert "10-bed ICU" in explanation
```

---

## Integration with Existing System

### Before This Change
```
hospital.csv → data_loader → trust_score (keyword-based) → ranker → explain
```

### After This Change
```
hospital.csv → data_loader → [LLM extraction] → cached extracted_data.jsonl
                                                         ↓
                                                    trust_score (evidence-based)
                                                         ↓
                                                    explain (with citations)
                                                         ↓
                                                    /search response
```

The extraction is a **one-shot offline step**. Once extracted_hospitals.jsonl exists, the online FastAPI flow is unchanged (just faster because it uses cached citations).

---

## API Response Changes

### Before
```json
{
  "hospital_id": "H_001",
  "name": "Bihar Rural Medical Center",
  "state": "Bihar",
  "matched_features": ["icu"],
  "trust_score": 75,
  "explanation": "Matched ICU; in Bihar, 12 km from PIN 800001; trust 75."
}
```

### After
```json
{
  "hospital_id": "H_001",
  "name": "Bihar Rural Medical Center",
  "state": "Bihar",
  "matched_features": ["icu"],
  "trust_score": 75,
  "trust_breakdown": [
    {
      "rule": "Has major specialty: icu",
      "delta": 20,
      "evidence": "Recently installed a 10-bed ICU with 4 ventilators and oxygen supply"
    },
    {
      "rule": "Has equipment: ventilator, oxygen",
      "delta": 20,
      "evidence": "10-bed ICU with 4 ventilators and oxygen supply"
    },
    {
      "rule": "Staffing model documented: mixed",
      "delta": 20,
      "evidence": "Dr. Sharma (MD, Internal Medicine) heads the ICU; 2 nurses on rotation"
    }
  ],
  "explanation": "✓ ICU: \"Recently installed a 10-bed ICU with 4 ventilators and oxygen supply\" | Has major specialty: icu (+20) — \"Recently installed a 10-bed ICU...\" | ⚠️ MEDIUM: Only 1 ICU doctor and 2 nurses listed; potential understaffing for critical care."
}
```

---

## What the Judges Will See

1. **Discovery & Verification:** Hospital capabilities extracted from free-form notes ✅
2. **IDP Innovation:** LLM-powered parsing with structured output ✅
3. **Contradictions detected:** Extracted data flags mismatches with evidence ✅
4. **Citations everywhere:** Every trust score rule has a source sentence ✅
5. **Traceability:** Users can click through to see exact evidence ✅

---

## Debugging / Monitoring

**In main.py logs:**
```
INFO: Loading extracted hospital data...
INFO: Loaded extracted data for 9,850 hospitals
WARNING: 150 hospitals missing extraction (may have failed during batch)
```

**In extraction.py logs:**
```
INFO: Extracting hospital H_001...
INFO: ✓ 12 tokens, 0.2s, confidence: 0.92
INFO: Extracting hospital H_002...
ERROR: API rate limit. Retrying (1/3)...
```

**Debug endpoint (optional):**
```python
@app.get("/debug/hospital/{hospital_id}")
def debug_hospital(hospital_id: str):
    hospital = app.state.df.loc[hospital_id]
    extracted = app.state.extracted_dict.get(hospital_id)
    score, breakdown = compute_trust_score(hospital, extracted)
    return {
        "hospital": hospital.to_dict(),
        "extracted": extracted,
        "trust_score": score,
        "breakdown": breakdown
    }
```

---

## Success Criteria

✅ Extract runs without errors on all 10k hospitals  
✅ extracted_hospitals.jsonl saves successfully  
✅ /search endpoint returns trust_breakdown with evidence fields  
✅ Explanations include exact quotes from hospital notes  
✅ No regression in ranking quality (top results still correct)  
✅ Performance: /search still returns in <500ms (extraction is cached)  
✅ Manual review: Pick 10 random results and verify citations are accurate  

---

## Questions for Cursor

If anything is unclear:
1. Are there existing tests I should follow for naming/structure?
2. Should extracted data be stored alongside the FAISS index or separately?
3. Do you want a progress bar during batch extraction?
4. Should failed extractions be retried, or logged and skipped?
