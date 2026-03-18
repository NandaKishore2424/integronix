# ICD-10-CM FY2026 Source Dataset Notes

## Scope
This document summarizes the FY2026 ICD-10-CM source datasets downloaded from CMS and extracted under ICD-data. It describes structure, field layouts, and how each source should be used in a deterministic ingestion pipeline.

## Source Files (Local Paths)
- ICD-data/icd10orderfiles/icd10cm_codes_2026.txt
- ICD-data/icd10orderfiles/icd10cm_order_2026.txt
- ICD-data/table-and-index/Table and Index/icd10cm_tabular_2026.xml
- ICD-data/table-and-index/Table and Index/icd10cm_index_2026.xml

## 1) icd10cm_codes_2026.txt (Code + Description)
Purpose: fast, flat list of all ICD-10-CM codes with their long descriptions.

Format: fixed-width, dotless codes.
- Columns
  - [1–7] Code (dotless)
  - [8] Space
  - [9–end] Description

Example
A000    Cholera due to Vibrio cholerae 01, biovar cholerae

Notes
- No hierarchy or billable flags.
- Best used as primary source for long descriptions.

## 2) icd10cm_order_2026.txt (Ordering + Billable Flag)
Purpose: ordering, short/long descriptions, and billable flag.

Format: fixed-width, dotless codes.
- Columns
  - [1–5] Order number
  - [6] Space
  - [7–13] Code (dotless)
  - [14] Space
  - [15] Billable flag (0 = header/non-billable, 1 = billable/leaf)
  - [16] Space
  - [17–76] Short description
  - [77] Space
  - [78–end] Long description

Notes
- Required for billable logic and deterministic leaf detection.
- Contains expanded 7th-character variants (e.g., laterality extensions).

## 3) icd10cm_tabular_2026.xml (Hierarchy and Coding Rules)
Purpose: ground truth for ICD-10-CM structure and hierarchy.

Key structure
- <chapter> with <name> and <desc>
- <section id="A00-A09"> with <desc>
- Recursive <diag> nodes:
  - <name> = code (dotted)
  - <desc> = description
  - nested <diag> = parent-child relationship

Rule-bearing elements (may appear at chapter/section/diag levels)
- <includes>, <inclusionTerm>
- <excludes1>, <excludes2>
- <useAdditionalCode>
- <codeFirst>
- <codeAlso>
- <sevenChrNote>, <sevenChrDef> with <extension char="…">

Notes
- Hierarchy must be derived only from nested <diag> structure.
- 7th-character rules are defined here; expanded billable codes appear in the order file.
- Codes in XML are dotted; normalize to dotless for joins.

## 4) icd10cm_index_2026.xml (Index to Diseases and Injuries)
Purpose: semantic lookup mapping from human terms to ICD codes.

Key structure
- <letter> groups by alphabet (not a hierarchy)
- <mainTerm> is a top-level term
  - <title> term text
  - optional <code>
  - optional <see> or <seeAlso>
  - nested <term level="…"> for refined phrase combinations

Interpretation
- This file is a search/lookup tree, not a clinical hierarchy.
- Build term phrases by concatenating the path of titles.
- <see> indicates redirection to another term.

Notes
- Use to build a search index table mapping term phrases to codes.
- Do not infer hierarchy or billability from this file.

## Normalization Rules (Deterministic)
- Store both dotted and dotless code representations.
  - code_raw: dotless (join key)
  - code_display: dotted (presentation)
- Hierarchy: XML <diag> nesting only.
- Billable: order file flag only.
- 7th-character logic: from <sevenChrNote>/<sevenChrDef>, validated against order file expansions.

## Recommended Use by Source
- Descriptions: icd10cm_codes_2026.txt
- Billable + ordering: icd10cm_order_2026.txt
- Hierarchy + rules: icd10cm_tabular_2026.xml
- Search mapping: icd10cm_index_2026.xml
