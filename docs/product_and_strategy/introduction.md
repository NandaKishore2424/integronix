# 1 Introduction

## 1.1 Purpose

This document provides a comprehensive architectural overview of the **CodePerfect Integronix** system, using a number of different architectural views to depict different aspects of the system. It is intended to capture and convey the significant architectural decisions, which have been made on the system, specifically aligned with the requirements for the Virtusa hackathon and the Ayushman Bharat Digital Mission (ABDM) compliance for the Indian healthcare ecosystem. The architecture defines how unstructured clinical text and discharge summaries are processed into standardized ICD-10 and ICD-11 codes.

## 1.2 Scope

This architecture document covers the core capabilities and structural design of the Integronix system. 
**In Scope:**
* The end-to-end clinical text extraction and coding pipeline using the LangGraph AI framework.
* Integration with the official World Health Organization (WHO) International Classification of Diseases (ICD) API v2 as the primary coding engine.
* The multi-tenant architecture designed to support multiple hospitals, branches, and users via Supabase Row-Level Security (RLS).
* Fallback mechanisms including vector-based similarity search matching.
* Cloud deployment architecture utilizing GCP Cloud Run for the backend and Vercel for the Next.js frontend.

**Out of Scope:**
* Detailed UI/UX design wireframes.
* Real-world financial integrations with private payer portals or TPA APIs.
* Deep-dive documentation on the internals of the underlying LLM (LLaMA 3.3-70B) itself.

## 1.3 Definitions, Acronyms and Abbreviations

**ABDM** - Ayushman Bharat Digital Mission. India's national digital health ecosystem framework.

**API** - Application Programming Interface. A set of functions allowing applications to access data and interact with external software components or operating systems.

**CC / MCC** - Complication or Comorbidity / Major Complication or Comorbidity. Codes that increase the reimbursement weight of a hospital stay.

**DRG** - Diagnosis-Related Group. A system to classify hospital cases into groups expected to have similar hospital resource use.

**FHIR** - Fast Healthcare Interoperability Resources. A standard describing data formats and elements and an application programming interface for exchanging electronic health records.

**GCP** - Google Cloud Platform.

**ICD-10 / ICD-11** - International Classification of Diseases (10th and 11th Revisions). Maintained by the WHO. ICD-11 is the latest standard mandated by ABDM.

**IndEA** - India Enterprise Architecture Framework. Framework guiding the development of digital health infrastructure.

**LangGraph** - An extension of LangChain for building stateful, multi-actor applications with LLMs.

**LLM** - Large Language Model (e.g., LLaMA 3.3-70B via Groq).

**MMS** - Mortality and Morbidity Statistics. The primary linearization of ICD-11 used for clinical coding and billing.

**OCR** - Optical Character Recognition. Used via Tesseract to extract text from scanned PDFs.

**RLS** - Row-Level Security. A database feature restricting which rows in a table are returned or updated based on the user executing the query.

**SNOMED CT** - Systematized Nomenclature of Medicine - Clinical Terms. An organized collection of medical terms used in clinical documentation.

## 1.4 References

1. World Health Organization (WHO). *ICD-API Version 2 Documentation*. Available from: `https://icd.who.int/docs/icd-api/APIDoc-Version2/`
2. National Health Authority (NHA), Government of India. *Ayushman Bharat Digital Mission (ABDM) Architecture*. Available from: `https://abdm.gov.in/`
3. HL7 International. *Fast Healthcare Interoperability Resources (FHIR) Release 4*. Available from: `http://hl7.org/fhir/R4/`
4. LangChain. *LangGraph Fundamentals*. Available from: `https://python.langchain.com/docs/langgraph`
5. Supabase. *Row Level Security (RLS) Guide*. Available from: `https://supabase.com/docs/guides/auth/row-level-security`
6. Integronix Internal Document: `docs/27_who_icd_api_integration_reference.md`
