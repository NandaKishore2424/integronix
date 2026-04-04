# LangGraph: The "Brain" of Our AI Pipeline Explained

## What is LangGraph? A Simple Analogy

Imagine a patient's chart in a hospital. This chart doesn't just stay in one place; it moves through a series of specialists in a specific order.

1.  **Admission Desk (Node 1)**: A clerk takes the patient's physical file (a PDF) and transcribes the important information into a new, clean digital chart (`raw_text`).
2.  **Triage Nurse (Node 2)**: An experienced nurse (our LLM) reads the transcribed notes and, using their broad knowledge, summarizes the key issues: "Looks like diabetes with kidney problems." They write this summary in the chart (`structured_entities`).
3.  **Specialist Coordinator (Nodes 4 & 5)**: This coordinator looks at the nurse's summary.
    - If the hospital has a special "Diabetes-Kidney" protocol (our `snomed_icd_map`), they send the chart directly to the Nephrology department.
    - If not, they send the chart to a general diagnostics lab for more tests (our `icd_embedding` vector search).
4.  **Attending Physician (Node 7)**: The physician (our `icd_decision` engine) looks at all the test results and specialist notes (`candidate_icd_codes`). They make the final, official diagnosis (`final_icd_code`). They are the expert and have the final say; they don't just guess.
5.  **Auditor & Billing Dept (Nodes 8, 9, 10)**: Finally, the chart goes to auditors and the billing department, who check the work, assess any risks, and calculate the costs (`audit`, `risk`, `financial` nodes).

**LangGraph is the hospital's system of pneumatic tubes and protocols.** It's the underlying framework that ensures the patient's chart (`CodingState`) moves from specialist to specialist (the `nodes`) in the correct order, that their findings are added to the chart, and that the chart takes different paths based on the diagnosis. It's a backend Python library that orchestrates this entire complex workflow.

---

## Why Not Just Use a Single Big LLM?

A simple AI application might look like this: `User's Question -> LLM -> Answer`. This is like asking a single, very smart intern to handle the entire patient journey from admission to billing. It's risky and unreliable for several reasons:

-   **Lack of Specialization**: The intern might be great at summarizing notes but terrible at understanding billing codes.
-   **No Audit Trail**: If they make a mistake, it's hard to know *where* in the process it happened.
-   **Risk of "Hallucination"**: The intern might "hallucinate" a diagnosis that isn't supported by the evidence because they're trying to be helpful. This is unacceptable in medical coding.
-   **Inflexibility**: You can't easily add a new specialist or change the workflow.

Our LangGraph approach solves this by creating a **"separation of concerns."**
-   The LLM does what it's good at: **reasoning** and understanding unstructured text (the Triage Nurse).
-   Deterministic, rule-based Python code does what it's good at: **making precise, auditable decisions** based on facts (the Attending Physician and Auditors).

---

## The Three Core Components of Our LangGraph Implementation

### 1. The State Object (`CodingState`)
This is the patient's chart. It's a Python dictionary that is passed to every single node. Each node reads information from it and writes its own findings back to it. This creates a complete, step-by-step record of the entire process.

### 2. The Nodes (The "Agents" or "Specialists")
Each node is just a Python function that performs one specific task.
-   `doc_processing_node`: Extracts text.
-   `clinical_extraction_agent`: Calls the LLM to understand the text.
-   `icd_decision_node`: Applies a scoring algorithm to select the best code.
-   `risk_scoring_node`: Applies a set of rules to calculate a risk score.

### 3. The Edges (The "Workflow" or "Protocols")
These are the connections that define the path the `CodingState` chart takes through the nodes.
-   **Standard Edges**: "After the `clinical_extraction` node, always go to the `cpt_resolver` node."
-   **Conditional Edges**: This is the most powerful feature. We define logic that changes the path based on the data. For example:
    > "After the `snomed_icd_map` node, check the `CodingState`. If the `candidate_icd_codes` list is full, go directly to the `icd_decision` node. If it's empty, you must first go to the `icd_embedding` node to find some candidates."

This conditional logic is what makes our system so robust and intelligent.

**[See the Full Pipeline Diagram Here](./diagrams.md#3-agent-architecture-diagram-langgraph-pipeline)**

---

## Benefits of Using LangGraph

| Benefit | Why It Matters for Integronix |
|---|---|
| **Auditability & Explainability** | Because the `CodingState` is saved after every run, we have a perfect, step-by-step record of every decision the AI made. We can show clients *exactly* why a certain code was chosen. |
| **Reliability & No Hallucinations** | By isolating the final decision to a deterministic, rule-based node (`icd_decision_node`), we completely eliminate the risk of the LLM inventing a code. The final output is always based on verifiable data. |
| **Modularity & Extensibility** | If we want to add a new step (e.g., a "Payer-Specific Rules" node), we can easily add it to the graph without having to rewrite the entire system. We can also swap out components (e.g., change the LLM provider) with minimal disruption. |
| **Flexibility** | The conditional routing allows us to handle different workflows (ICD-10 vs. ICD-11) and complex fallback logic (semantic search) within a single, elegant structure. |

In short, LangGraph allows us to build a system that is not just "smart," but also **safe, reliable, and transparent.**

