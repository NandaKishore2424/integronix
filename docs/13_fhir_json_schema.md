# 13 — FHIR-Aligned Internal JSON Schema

## Design Philosophy

- We do NOT build a full FHIR server (that's enterprise Phase 4)
- We DO align our internal JSON structures to FHIR resource shapes
- This ensures interoperability readiness and impresses technically-aware judges
- All internal API responses and DB JSONB fields follow FHIR-adjacent structure

---

## Why FHIR Alignment Matters

FHIR (Fast Healthcare Interoperability Resources) is the modern standard for healthcare data exchange. Hospitals, payers, and EHR vendors (Epic, Cerner, Athena) all use FHIR-compatible APIs. Designing our schema to align with FHIR means:

- Future EHR integration is straightforward (not a rewrite)
- Judges recognize we understand healthcare interoperability
- Data is extensible without breaking changes

---

## FHIR Resources We Align With

| FHIR Resource | What We Use It For |
|---|---|
| `Encounter` | One clinical document / patient visit |
| `Condition` | A single diagnosis extracted from the document |
| `Procedure` | CPT-coded services (Phase 2) |
| `Observation` | Lab values that influence specificity (LOINC) |
| `Claim` | Billing representation for revenue calculation |

---

## Internal JSON Schemas

### 1. Clinical Case (Encounter-Aligned)

Stored as a session record in Supabase. The `structured_entities` JSONB field uses this shape.

```json
{
  "resourceType": "Encounter",
  "id": "enc-3f8a7b2c-...",
  "status": "finished",
  "class": {
    "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
    "code": "IMP",
    "display": "inpatient"
  },
  "subject": {
    "reference": "Patient/patient-uuid"
  },
  "period": {
    "start": "2024-01-10",
    "end": "2024-01-15"
  },
  "conditions": [],
  "procedures": [],
  "observations": []
}
```

---

### 2. Condition (Diagnosis — Core Resource)

This is what the Clinical Extraction Agent outputs.

```json
{
  "resourceType": "Condition",
  "id": "cond-uuid",
  "clinicalStatus": {
    "coding": [
      {
        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
        "code": "active"
      }
    ]
  },
  "verificationStatus": {
    "coding": [
      {
        "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
        "code": "confirmed"
      }
    ]
  },
  "category": [
    {
      "coding": [
        {
          "system": "http://terminology.hl7.org/CodeSystem/condition-category",
          "code": "encounter-diagnosis"
        }
      ]
    }
  ],
  "code": {
    "coding": [
      {
        "system": "http://snomed.info/sct",
        "code": "44054006",
        "display": "Diabetes mellitus type 2"
      }
    ],
    "text": "Type 2 diabetes mellitus with chronic kidney disease"
  },
  "severity": {
    "coding": [
      {
        "system": "http://snomed.info/sct",
        "code": "6736007",
        "display": "Moderate"
      }
    ]
  },
  "onsetDateTime": "2024-01-10",
  "evidence": [
    {
      "detail": [
        {
          "display": "Patient has elevated creatinine and eGFR 42 consistent with CKD Stage 3"
        }
      ]
    }
  ],
  "extension": [
    {
      "url": "https://integronix.io/fhir/StructureDefinition/icd-mapping",
      "valueCodeableConcept": {
        "coding": [
          {
            "system": "http://hl7.org/fhir/sid/icd-10-cm",
            "code": "E11.22",
            "display": "Type 2 diabetes mellitus with diabetic chronic kidney disease"
          }
        ],
        "text": "Deterministically selected from ICD-10-CM 2024"
      }
    }
  ]
}
```

**Key design decisions:**
- SNOMED code captures clinical meaning
- ICD-10 mapping is stored in a FHIR extension field (not the core code field)
- Evidence linking is preserved — this powers the audit explainability

---

### 3. Comorbidity (Secondary Condition)

Each comorbidity extracted by the LLM is its own Condition resource, linked to the encounter.

```json
{
  "resourceType": "Condition",
  "id": "cond-comorbidity-uuid",
  "code": {
    "coding": [
      {
        "system": "http://snomed.info/sct",
        "code": "709044004",
        "display": "Chronic kidney disease stage 3"
      }
    ],
    "text": "CKD Stage 3"
  },
  "clinicalStatus": {
    "coding": [{ "code": "active" }]
  },
  "category": [
    {
      "coding": [{ "code": "problem-list-item" }]
    }
  ],
  "extension": [
    {
      "url": "https://integronix.io/fhir/StructureDefinition/icd-mapping",
      "valueCodeableConcept": {
        "coding": [
          {
            "system": "http://hl7.org/fhir/sid/icd-10-cm",
            "code": "N18.3",
            "display": "Chronic kidney disease, stage 3"
          }
        ]
      }
    }
  ]
}
```

---

### 4. Observation (Lab-Based Specificity, LOINC)

Used when lab values inform the ICD specificity decision.

```json
{
  "resourceType": "Observation",
  "id": "obs-egfr-uuid",
  "status": "final",
  "code": {
    "coding": [
      {
        "system": "http://loinc.org",
        "code": "33914-3",
        "display": "Glomerular filtration rate (eGFR)"
      }
    ]
  },
  "valueQuantity": {
    "value": 42,
    "unit": "mL/min/1.73m2",
    "system": "http://unitsofmeasure.org"
  },
  "interpretation": [
    {
      "coding": [
        {
          "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
          "code": "L",
          "display": "Low"
        }
      ]
    }
  ],
  "note": [
    {
      "text": "eGFR 42 consistent with CKD Stage 3 — used to inform ICD code specificity"
    }
  ]
}
```

---

### 5. Claim (Revenue Representation)

Represents the billing output after ICD mapping.

```json
{
  "resourceType": "Claim",
  "id": "claim-uuid",
  "status": "active",
  "type": {
    "coding": [
      {
        "system": "http://terminology.hl7.org/CodeSystem/claim-type",
        "code": "institutional"
      }
    ]
  },
  "diagnosis": [
    {
      "sequence": 1,
      "type": [
        {
          "coding": [{ "code": "principal" }]
        }
      ],
      "diagnosisCodeableConcept": {
        "coding": [
          {
            "system": "http://hl7.org/fhir/sid/icd-10-cm",
            "code": "E11.22",
            "display": "Type 2 diabetes mellitus with diabetic chronic kidney disease"
          }
        ]
      }
    },
    {
      "sequence": 2,
      "type": [
        {
          "coding": [{ "code": "secondary" }]
        }
      ],
      "diagnosisCodeableConcept": {
        "coding": [
          {
            "system": "http://hl7.org/fhir/sid/icd-10-cm",
            "code": "N18.3"
          }
        ]
      }
    }
  ],
  "total": {
    "value": 2100.00,
    "currency": "USD"
  },
  "meta": {
    "tag": [
      {
        "system": "https://integronix.io/fhir/tags",
        "code": "ai-suggested",
        "display": "AI-suggested claim — pending human review"
      }
    ]
  }
}
```

---

## Audit Result Object (Integronix-Specific Extension)

This is not a standard FHIR resource but follows FHIR extension conventions.

```json
{
  "resourceType": "Basic",
  "code": {
    "coding": [
      {
        "system": "https://integronix.io/fhir/CodeSystem/resource-types",
        "code": "CodingAuditResult"
      }
    ]
  },
  "extension": [
    {
      "url": "https://integronix.io/fhir/StructureDefinition/ai-code",
      "valueString": "E11.22"
    },
    {
      "url": "https://integronix.io/fhir/StructureDefinition/human-code",
      "valueString": "E11.9"
    },
    {
      "url": "https://integronix.io/fhir/StructureDefinition/discrepancy-type",
      "valueString": "SPECIFICITY_IMPROVEMENT"
    },
    {
      "url": "https://integronix.io/fhir/StructureDefinition/evidence-text",
      "valueString": "Patient has eGFR 42 consistent with CKD Stage 3 as documented in labs"
    },
    {
      "url": "https://integronix.io/fhir/StructureDefinition/revenue-delta",
      "valueMoney": {
        "value": 450.00,
        "currency": "USD"
      }
    },
    {
      "url": "https://integronix.io/fhir/StructureDefinition/risk-label",
      "valueString": "MEDIUM"
    }
  ]
}
```

---

## Supabase Storage Strategy

All FHIR-aligned JSON objects are stored in Supabase JSONB columns:

| Table | Column | Content |
|---|---|---|
| `clinical_cases` | `structured_entities` | Array of FHIR `Condition` objects |
| `clinical_cases` | `observations` | Array of FHIR `Observation` objects |
| `coding_results` | `claim_json` | FHIR `Claim` object |
| `audit_log` | `audit_result_json` | Integronix Audit Result extension |

---

## What to Say in Pitch

> *"Our internal data schema aligns with FHIR Condition, Observation, and Claim resources to ensure healthcare interoperability readiness. SNOMED codes capture clinical meaning while ICD-10 codes are stored in FHIR extension fields after deterministic mapping. This design allows straightforward EHR integration in production without schema rewrites."*
