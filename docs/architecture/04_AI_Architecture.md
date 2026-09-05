# AI Architecture

**Document:** 04_AI_Architecture.md

**Status:** Active

**Date:** 2026-08-05

---

## 1. Purpose

This document defines the intelligence operating model of ScholarOS. It explains how the system thinks, reasons, remembers, and coordinates work across the research workflow.

This document is a logical architecture. It describes the structure, responsibilities, and interactions of the intelligence layer without prescribing algorithms, model selection, prompt formats, code structure, or provider-specific behavior. It complements the Milestone 1 architecture set:

* [01_Architecture_Overview.md](01_Architecture_Overview.md) — overall layered architecture
* [02_System_Components.md](02_System_Components.md) — conceptual components
* [03_Data_Architecture.md](03_Data_Architecture.md) — conceptual data domains

The intelligence layer described here realizes the Intelligence Coordination, Context Assembly, Retrieval, Knowledge Management, Project Memory, and Drafting capabilities introduced in those documents.

---

## 2. AI Philosophy

ScholarOS treats intelligence as an orchestrated research capability, not as a single generation act.

The philosophy of the intelligence layer is:

* **Understand before generation.** The system must establish sufficient understanding of the project before producing substantive assistance.
* **Evidence before assertion.** Every substantive claim must be traceable to the user's project materials.
* **Assist, do not replace.** The researcher remains the intellectual owner and final authority.
* **Preserve the author's voice.** Assistance must align with the author's established characteristics without copying prior work verbatim.
* **Remember across sessions.** Project understanding, decisions, and context persist and accumulate.
* **Remain replaceable.** The intelligence layer is provider-agnostic and modular.

This philosophy is derived from the Vision Document and enforced by SRS Chapter 6 (AIR-001 to AIR-003) and the AI operating principles in Section 3 below.

---

## 3. AI Operating Principles

The intelligence layer operates under the following principles:

* **Separation of stages.** Reasoning, context construction, generation, and review remain distinct, coordinated stages (AIR-004).
* **Continuity of understanding.** Iterative interaction must not lose project understanding between steps (AIR-005).
* **Distinction of artifacts.** Raw input, interpreted knowledge, stored memory, and approved output remain distinguishable (AIR-006).
* **Grounding.** Substantive outputs are grounded in retrieved or otherwise available evidence (AIR-025).
* **Confidence honesty.** Supported evidence, inferred interpretation, and unresolved uncertainty are distinguished and presented as such (AIR-067, AIR-068).
* **Explainability.** Outputs must be interpretable and their derivation reviewable (AIR-049 to AIR-051).
* **Human oversight.** Every output remains reviewable, editable, and approvable (AIR-037).
* **Provider agnosticism.** External services are interchangeable through a consistent conceptual contract (AIR-040 to AIR-042).

---

## 4. Position in the Overall Architecture

The intelligence layer corresponds to the Intelligence Layer of the layered architecture in [01_Architecture_Overview.md](01_Architecture_Overview.md) and realizes the behavior of the Intelligence Coordination Component, Context Assembly Component, Retrieval Component, Knowledge Management Component, and Drafting Support Component defined in [02_System_Components.md](02_System_Components.md).

It operates on the data domains defined in [03_Data_Architecture.md](03_Data_Architecture.md): the user's Agent workspace, its one project, documents, knowledge, knowledge chunks, memory, conversations, writing profiles, drafts, and reviews. **Corrected by ADR-009:** the intelligence layer's capability registry (previously "agents" here) is renamed "capabilities" throughout this document; "Agent" now refers to the user's workspace, which most of the entities in this list are scoped to (§13, §14).

The layer is intentionally organized so that its capabilities can evolve independently (AIR-058 to AIR-060) and can be configured without altering the product contract (AIR-055).

---

## 5. AI Lifecycle

The intelligence layer operates as a structured lifecycle rather than a request-response interaction (AIR-063, AIR-064).

### 5.1 Intelligence Lifecycle Stages

| Stage | Responsibility | Primary Requirements |
|-------|---------------|----------------------|
| 1. User intent | Interpret the current task, objective, and constraints | AIR-001 |
| 2. Knowledge understanding | Maintain a working understanding of the research domain | AIR-007 to AIR-009 |
| 3. Knowledge interpretation | Distinguish relevance, conflicts, and project-specific meaning | AIR-010 to AIR-012 |
| 4. Memory integration | Incorporate persistent project context | AIR-019 to AIR-021, AIR-065, AIR-066 |
| 5. Author profile integration | Apply stylistic characteristics without imitation | AIR-016 to AIR-018 |
| 6. Context construction | Assemble a task-specific working context | AIR-013 to AIR-015 |
| 7. Reasoning | Process context against the task objective | AIR-002, AIR-063 |
| 8. Draft assistance | Generate or refine evidence-grounded content | AIR-031 to AIR-036 |
| 9. Human review | Present outputs for evaluation, revision, and approval | AIR-037 to AIR-039 |
| 10. Project continuity | Update memory and preserve context for later stages | AIR-020, AIR-065 |

Each stage may feed subsequent stages; outputs remain subject to human oversight throughout (AIR-064).

### 5.2 Research Workflow Alignment

The intelligence lifecycle maps directly onto the ScholarOS research journey defined in the SRS workflows:

```
Agent Creation (the user's workspace, with its one permanent Project — ADR-009)
        ↓
Document Collection
        ↓
Knowledge Processing
        ↓
Knowledge Chunking
        ↓
Memory Building
        ↓
Research Conversations
        ↓
Capability Binding
        ↓
Writing
        ↓
Review
        ↓
Revision
        ↓
Export
        ↓
Long-term Project Memory
```

**Corrected by ADR-009:** the journey now opens with Agent Creation (the user's permanent workspace), replacing the prior opening step "Project Creation" — Project is created together with its Agent as the raw input material, not as a separate first step. The step formerly named "Agent Creation" mid-journey (binding intelligence capabilities) is renamed "Capability Binding" to avoid collision with the new opening step.

Each step of this journey is served by a corresponding intelligence capability: intake (Document Collection) is followed by the Knowledge Processing Pipeline, knowledge chunking produces retrievable units, memory building populates the Memory Architecture, research conversations activate the Conversation and Research Intelligence capabilities, capability binding binds capabilities through the Capability Registry, and writing, review, revision, and export are served by the Writing, Review, and Reflection capabilities. The cycle closes by writing outcomes back into Long-term Project Memory.

---

## 6. Context Assembly Pipeline

The Context Assembly Pipeline constructs the task-specific working context that precedes reasoning and generation.

### 6.1 Inputs

* Current user objective and drafting/review task (WR-016)
* Retrieved knowledge and evidence from the project knowledge base (AIR-022)
* Persistent project memory (AIR-019)
* Author profile signals (AIR-016)
* Current project state and workflow position (AIR-014)

### 6.2 Processing

The pipeline combines inputs into a coherent context while preserving provenance so that each element remains traceable to its source (AIR-052, AIR-053).

The pipeline distinguishes:

* persistent project knowledge from temporary drafting context (AIR-066);
* current project state from historical context (AIR-021);
* supported evidence from inferred interpretation (AIR-026, AIR-067).

### 6.3 Outputs

* An assembled working context suitable for reasoning or drafting
* A reviewable context artifact presented to the user before execution (WR-018, MVP-014)
* A structured basis for downstream drafting and review

### 6.4 Interactions

* Receives inputs from the Retrieval Strategy, Memory Architecture, and Author Profile capability
* Supplies assembled context to the Prompt Management capability and the Writing and Review Pipelines
* Reports context quality back to the Reflection Loop

---

## 7. Knowledge Processing Pipeline

The Knowledge Processing Pipeline transforms uploaded research materials into structured, reusable knowledge.

### 7.1 Stages

1. **Material acceptance.** Registered source documents enter the pipeline (WR-004, MVP-003).
2. **Conceptual extraction.** The pipeline derives concepts, themes, methods, claims, and relationships from source material (AIR-007, AIR-008, MVP-005).
3. **Relationship recognition.** Connections among concepts, claims, methods, and evidence are identified (AIR-009).
4. **Relevance classification.** Extracted elements are assessed against the project's evolving objectives (AIR-010).
5. **Structuring.** Knowledge is organized into coherent relationships and categories (MVP-006, DR-007 to DR-009).
6. **Evidence linkage.** Every knowledge element retains traceability to its source material (AIR-024, DR-008).

### 7.2 Guiding Principles

* Interpretation is grounded in project context, not generic patterns (AIR-012).
* Knowledge processing supports classification, comparison, and synthesis (AIR-011).
* Knowledge quality depends on the quality of user-supplied materials; completeness is not guaranteed (MVP scope limitation).
* New materials may refine or supersede prior understanding (AIR-065).

### 7.3 Interactions

* Consumes registered documents from the Document capability
* Produces knowledge elements and evidence linkages consumed by the Knowledge Chunking Architecture
* Feeds the Retrieval Strategy and Memory Architecture

---

## 8. Memory Architecture

The Memory Architecture preserves persistent project understanding across sessions and activities.

### 8.1 Memory Layers

| Layer | Content | Requirements |
|-------|---------|--------------|
| Project memory | Objectives, hypotheses, methodological decisions, terminology, institutional guidance, decision chronology | AIR-019 to AIR-021, WR-013 to WR-015, DR-013 to DR-015 |
| Working context | Temporary, task-specific assembly | AIR-066 |
| Historical record | Prior decisions and context that inform without overriding current intent | AIR-021, DR-014 |
| Conversation memory | Interaction history preserved for continuity | WR-034; per [03_Data_Architecture.md](03_Data_Architecture.md), Conversations domain |

### 8.2 Memory Behaviors

* **Capture.** Memory is populated through user input and system-derived context (WR-013, MVP-011).
* **Retrieval.** Relevant memory elements are recalled when constructing context (WR-017, MVP-011).
* **Update.** Memory evolves as the project progresses (WR-015, MVP-012, AIR-065).
* **Supersession.** New decisions may supersede older ones while historical traceability is retained (AIR-021, DR-014).

### 8.3 Interactions

* Receives decisions, review outcomes, and workflow context
* Supplies persistent context to the Context Assembly Pipeline and the Writing Pipeline
* Receives reflection outputs from the Reflection Loop

---

## 9. Knowledge Chunking Architecture

Knowledge chunking divides processed knowledge into discrete, retrievable units that support focused retrieval and evidence-grounded assistance.

### 9.1 Chunking Principles

* Chunks are units of interpreted knowledge, not raw text fragments.
* Each chunk carries provenance: the source document(s) and knowledge relationships it derives from (DR-006, DR-008).
* Chunks support focused retrieval for specific tasks or questions (MVP-007).
* Chunks remain linked to broader knowledge structures and project memory.
* Chunk boundaries follow conceptual and thematic coherence rather than fixed mechanical sizes.

### 9.2 Chunk Lifecycle

* Created during knowledge processing.
* Relinked or revised as project knowledge evolves.
* Retained while relevant to the project's understanding; eligible for controlled removal per data lifecycle rules (DR-023 to DR-025).

### 9.3 Interactions

* Receives structured knowledge from the Knowledge Processing Pipeline
* Supplies retrievable units to the Retrieval Strategy and Context Assembly Pipeline

---

## 10. Conversation Intelligence

Conversation Intelligence governs how ScholarOS interacts with the researcher through research conversations.

### 10.1 Responsibilities

* Interpret user intent and clarify ambiguous direction (AIR-001).
* Maintain continuity of understanding across sequential and iterative interaction (AIR-005).
* Distinguish conversation-level requests from persistent project changes; only user-approved changes enter memory.
* Preserve conversation history as a continuity record (WR-034, conversation data domain).

### 10.2 Conversation Model

* Conversations occur within a project context and may reference documents, knowledge, drafts, and memory.
* Conversation flow supports the targeted workflow, allowing entry at any stage where context is sufficient (WR-031).
* Conversations may be summarized or linked to memory rather than stored verbatim indefinitely (per [03_Data_Architecture.md](03_Data_Architecture.md), Conversations domain).

### 10.3 Interactions

* Receives user requests and revision instructions
* Invokes the Research Intelligence capability for domain questions
* Informs the Planning Layer when a request requires multi-step execution
* Writes approved outcomes to the Memory Architecture

---

## 11. Research Intelligence

Research Intelligence is the capability that answers research questions, examines relationships, and supports understanding of the project domain.

### 11.1 Responsibilities

* Answer domain questions grounded in project knowledge (AIR-022, AIR-025).
* Compare, classify, and synthesize knowledge elements (AIR-011).
* Identify supported evidence, conflicting viewpoints, and unresolved questions (AIR-010, AIR-067, AIR-068).
* Support exploration of concepts and relationships across the knowledge base.

### 11.2 Guiding Constraints

* Research answers are grounded in retrieved project evidence; generic or decontextualized reasoning is avoided (AIR-012).
* Missing evidence and low-confidence conclusions are acknowledged explicitly (AIR-048).
* Research intelligence does not supplement project knowledge with external sources unless explicitly configured (MVP scope limitation).

### 11.3 Interactions

* Queries the Retrieval Strategy and Knowledge Chunking Architecture
* Supplies understanding to the Context Assembly Pipeline and Writing Pipeline
* Reports gaps and open questions to the Reflection Loop and Memory Architecture

---

## 12. Planning Layer

The Planning Layer decomposes complex requests into ordered, coordinated steps before execution.

### 12.1 Responsibilities

* Translate a research or drafting objective into a sequence of intelligence actions.
* Determine which capabilities (retrieval, reasoning, drafting, review) are required and in what order.
* Respect the "understand before generate" constraint: planning ensures context sufficiency before drafting is triggered (AIR-031).
* Preserve the distinction between planned steps and executed outcomes (AIR-006).

### 12.2 Planning Principles

* Plans are task-scoped and derived from the assembled context, not from a single instruction string (AIR-028).
* Plans remain visible and reviewable by the user before execution.
* Plans support iteration: a user may redirect, add evidence, or refine the plan without losing continuity (AIR-005).

### 12.3 Interactions

* Receives objectives from Conversation Intelligence and the Review Pipeline
* Invokes capabilities through Capability Orchestration (renamed from "Agent Orchestration" by ADR-009)
* Supplies execution context to the Context Assembly Pipeline

---

## 13. Capability Orchestration

**Renamed from "Agent Orchestration" by ADR-009**, to avoid collision with the new Agent workspace entity (`docs/database/02_Domain_Model.md` §4.13). Meaning and function unchanged.

Capability Orchestration coordinates the intelligence capabilities as a team of focused capabilities rather than a single monolithic actor.

### 13.1 Responsibilities

* Route work to the appropriate capability: understanding, retrieval, drafting, review, coordination.
* Manage the handoff of context and evidence between capabilities so that provenance is preserved.
* Maintain a coherent end-to-end workflow from intent to review (AIR-004).
* Keep human oversight in the loop at decision points (AIR-039).

### 13.2 Orchestration Model

* Orchestration is driven by the Planning Layer and constrained by the workflow state.
* Each capability operates within defined boundaries and returns structured, traceable results.
* The outcome of one stage may inform subsequent stages without discarding prior evidence or user intent (AIR-034).

### 13.3 Interactions

* Receives plans from the Planning Layer
* Invokes capabilities registered in the Capability Registry (renamed from "Agent Registry" by ADR-009)
* Reports execution context and results to the Reflection Loop

---

## 14. Capability Registry

**Renamed from "Agent Registry" by ADR-009**, to avoid collision with the new Agent workspace entity. Meaning and function unchanged.

The Capability Registry is the catalog of intelligence capabilities available to the orchestration layer.

### 14.1 Responsibilities

* Maintain an inventory of capabilities (e.g., knowledge processing, retrieval, drafting, review, coordination).
* Describe each capability's purpose, inputs, outputs, and boundaries.
* Enable controlled addition of new capabilities without invalidating the research workflow (AIR-058, AIR-059).
* Keep capabilities conceptually independent from any single workflow stage so future capabilities can be introduced through controlled extension (AIR-060).

### 14.2 Registry Model

* Capabilities are registered as named, replaceable units.
* Registration metadata supports discovery, routing, and explainability (AIR-049, AIR-050).
* The registry reflects configuration-approved capability sets (AIR-055, AIR-056).

### 14.3 Interactions

* Consumed by Capability Orchestration for capability selection
* Updated through the extensibility path when new capabilities are added
* Aligned with the Capability data domain in [03_Data_Architecture.md](03_Data_Architecture.md) (renamed from "Agent" by ADR-009)

---

## 15. Prompt Management

Prompt Management constructs the inputs that are presented to reasoning and generation capabilities. It is a structured capability, not an uncontrolled free-form command.

### 15.1 Responsibilities

* Construct task-specific prompts from the assembled context, not solely from a single user instruction (AIR-028).
* Include relevant project memory, author profile signals, and supporting evidence where appropriate (AIR-029).
* Remain explainable, reviewable, and aligned with the current user task (AIR-030).

### 15.2 Construction Principles

* Context quality drives output quality; prompting supplements rather than substitutes for assembled context.
* Prompts preserve provenance references so outputs can be traced to their inputs (AIR-052).
* Prompt construction is governed by configuration-approved workflow parameters (AIR-055) and remains consistent with the product contract regardless of provider (AIR-041).

### 15.3 Interactions

* Receives assembled context from the Context Assembly Pipeline
* Produces requests consumed by the Provider Abstraction boundary
* Receives revision inputs from the Review Pipeline for iterative refinement

---

## 16. Retrieval Strategy

The Retrieval Strategy governs how relevant knowledge and evidence are located and selected for a given task.

### 16.1 Responsibilities

* Retrieve relevant project knowledge and research evidence before substantive drafting support (AIR-022).
* Drive retrieval by the current project objective, knowledge base content, and task-specific context (AIR-023).
* Preserve traceability from retrieved knowledge to supporting source material (AIR-024, MVP-008).

### 16.2 Strategy Principles

* Retrieval is task-scoped and context-sensitive rather than a fixed global search.
* Multiple selection criteria may be combined: relevance to the task, relationship to the assembled context, and evidential strength.
* Retrieval results carry provenance and confidence distinctions (AIR-067).
* Retrieval operates only over user-supplied project knowledge unless external sources are explicitly configured (MVP scope limitation).

### 16.3 Interactions

* Queries the Knowledge Chunking Architecture and Memory Architecture
* Supplies retrieved evidence to the Context Assembly Pipeline
* Feeds evidence flow into the Citation and Evidence Flow capability

---

## 17. Context Window Management

Context Window Management governs how the assembled context is sized, ordered, and prioritized for use by reasoning and generation capabilities.

### 17.1 Responsibilities

* Fit the most relevant context within the operating limits of the underlying capability without degrading the task.
* Prioritize task-relevant knowledge, memory, and evidence over peripheral content (AIR-010).
* Preserve provenance for every element retained in the window.
* Support larger or multi-section contexts as the product evolves (roadmap: Phase 2 enhanced context assembly).

### 17.2 Management Principles

* Selection is driven by the task objective and the assembled context, not by arbitrary truncation.
* When the full relevant context exceeds capacity, prioritization and summarization decisions remain explainable (AIR-030, AIR-049).
* The distinction between persistent knowledge and temporary context is preserved (AIR-066).

### 17.3 Interactions

* Receives the assembled context from the Context Assembly Pipeline
* Produces the bounded, ordered context consumed by Prompt Management
* Reports context sufficiency back to the Planning Layer (AIR-031)

---

## 18. Citation and Evidence Flow

The Citation and Evidence Flow preserves the relationship between generated content and the evidence that supports it, end to end.

### 18.1 Flow Stages

1. **Evidence capture.** Source materials are registered with identity and metadata (DR-004, DR-005).
2. **Evidence linkage.** Knowledge and chunks carry references to source material (DR-008).
3. **Retrieval.** Evidence is selected with provenance intact (AIR-024).
4. **Draft association.** Draft content is annotated with the evidence and knowledge that support it (AIR-027, DR-018).
5. **Review visibility.** Evidence references are presented during review (WR-022).
6. **Output traceability.** Final content retains traceability for audit and revision (AIR-052 to AIR-054).

### 18.2 Responsibilities

* Prevent unsupported assertions from being presented as established facts (AIR-046).
* Distinguish supported knowledge, inferred interpretation, and open questions (AIR-067, AIR-068).
* Avoid fabricating source claims or findings not supported by project context (AIR-043).

### 18.3 Interactions

* Crosscuts the Knowledge Processing Pipeline, Retrieval Strategy, Writing Pipeline, and Review Pipeline
* Supplies evidence references to the Review Pipeline and the user-facing review experience

---

## 19. Review Pipeline

The Review Pipeline supports the evaluation of drafts and supporting context by the researcher.

### 19.1 Responsibilities

* Present drafts with evidence references and context for review (WR-022, AIR-037).
* Support the researcher in accepting, rejecting, revising, or requesting further grounding (AIR-039).
* Preserve review decisions, revision requests, and approval state (WR-025, DR-019).
* Record review outcomes that inform future drafting and memory (AIR-064).

### 19.2 Review Capabilities

* Evidence presence checks: surfaced claims are cross-checked against supporting references.
* Consistency awareness: drafts are assessed for alignment with project memory and prior decisions.
* Confidence disclosure: supported, inferred, and uncertain content is distinguished (AIR-047, AIR-067).
* Human decision points: approval remains the researcher's responsibility (AIR-003, AIR-038).

### 19.3 Interactions

* Receives drafts from the Writing Pipeline
* Receives evidence references from the Citation and Evidence Flow
* Outputs review outcomes to the Writing Pipeline (revision) and the Memory Architecture (decisions)

---

## 20. Writing Pipeline

The Writing Pipeline produces and refines draft content in an evidence-grounded, author-aligned manner.

### 20.1 Stages

1. **Context confirmation.** Drafting proceeds only when the assembled context is sufficient (AIR-031).
2. **Structure proposal.** The draft respects the researcher's intent, direction, and writing structure (AIR-032).
3. **Generation.** Draft content is produced from context, evidence, memory, and author profile signals (AIR-016, AIR-029).
4. **Evidence grounding.** Claims and assertions are tied to retrieved evidence (AIR-025, AIR-027).
5. **Refinement.** Successive revision cycles improve the draft without discarding underlying evidence and user intent (AIR-034).
6. **Version awareness.** Refinement preserves the relationship between current improvements and prior state (AIR-035, MVP-021).
7. **Review handoff.** The draft passes to the Review Pipeline with traceability intact (AIR-033).

### 20.2 Guiding Principles

* Draft generation is a deliberate act, not the first research act.
* Coherent improvement is favored over unconstrained re-generation (AIR-036).
* Author voice is preserved without replacing the author's intellectual ownership (AIR-017, AIR-018).

### 20.3 Interactions

* Receives context from the Context Assembly Pipeline and plans from the Planning Layer
* Queries evidence through the Citation and Evidence Flow
* Outputs drafts and revision options to the Review Pipeline

---

## 21. Reflection Loop

The Reflection Loop evaluates completed cycles and feeds learning back into the system.

### 21.1 Responsibilities

* Assess whether an executed cycle achieved its objective with adequate grounding and continuity.
* Identify gaps: missing evidence, unresolved questions, low-confidence areas (AIR-048).
* Detect context insufficiency that should have been flagged earlier (AIR-031).
* Produce improvement signals that update memory and inform future context assembly.

### 21.2 Reflection Principles

* Reflection is project-scoped, not user-general: it improves understanding of the project (per AIR-019 scope).
* Reflection outputs are advisory and subject to human oversight.
* Reflection never alters memory without user awareness (MVP-011 limitation).

### 21.3 Interactions

* Observes outcomes of the Writing, Review, and Research Intelligence capabilities
* Reports findings to the Memory Architecture and the Context Assembly Pipeline
* Raises open questions to the researcher through Conversation Intelligence

---

## 22. Learning and Memory Preservation

Learning and Memory Preservation is the capability through which the system improves its understanding of a project over time.

### 22.1 Responsibilities

* Refine project understanding as new knowledge becomes available (AIR-065).
* Preserve decisions, terminology, methodology, and research continuity across sessions (AIR-020, WR-014).
* Distinguish persistent project knowledge from temporary drafting context (AIR-066).
* Preserve chronology and change history (DR-014).

### 22.2 Learning Sources

* New documents and materials introduced by the user
* Reviewer feedback and revision decisions
* User refinements to knowledge and memory
* Approved conversation outcomes

### 22.3 Guiding Constraints

* Learning applies to the project, not to the user generally.
* Memory is populated through user input and system-derived context; the system shall not infer memory elements without user awareness (MVP-011 limitation).
* Historical context may inform current work without overriding present user intent (AIR-021).

### 22.4 Interactions

* Receives inputs from the Reflection Loop, Review Pipeline, and Conversation Intelligence
* Supplies persistent context to the Context Assembly Pipeline and Writing Pipeline

---

## 23. Provider Abstraction

Provider Abstraction insulates the intelligence layer from external AI services.

### 23.1 Responsibilities

* Maintain a consistent conceptual contract for reasoning, generation, and review independent of the external model or service (AIR-041).
* Enable provider substitution in a controlled and observable manner (AIR-042).
* Ensure the research workflow does not change when the underlying provider changes (AIR-040).

### 23.2 Abstraction Model

* All reasoning and generation capabilities interact with providers through a single abstract boundary.
* The boundary carries requests constructed by Prompt Management and returns structured responses for workflow integration.
* Provider selection and workflow parameters are configuration-governed (AIR-055, AIR-056) and reviewable (AIR-057).

### 23.3 Interactions

* Receives requests from Prompt Management and Agent Orchestration
* Returns responses to the Writing Pipeline and Research Intelligence capability
* Interfaces with the AI Provider Interface defined in SRS Chapter 9 (API-029 to API-031)

---

## 24. Failure Handling

Failure handling defines how the intelligence layer behaves when capabilities or providers fail.

### 24.1 Responsibilities

* Detect failures in retrieval, reasoning, generation, or provider interaction.
* Preserve the integrity of project knowledge and prevent silent data corruption (NFR-004).
* Provide clear feedback and recovery paths when an action cannot be completed (WR-036).
* Support degraded-mode behavior when a required service is temporarily unavailable (NFR-006).

### 24.2 Failure Categories

| Category | Behavior |
|----------|----------|
| Insufficient context | Drafting is deferred with an explanation; the user may enrich context (AIR-031) |
| Retrieval failure | The user is informed; unsupported generation is not substituted for missing evidence (AIR-044) |
| Provider failure | The request is retried or surfaced through configured degradation behavior (NFR-006) |
| Low-confidence outcome | Confidence boundaries are disclosed rather than presented as fact (AIR-047, AIR-068) |

### 24.3 Interactions

* Reports status to the user through Conversation Intelligence
* Records failure context in observability channels (NFR-027, NFR-028)
* Prevents partial or misleading outputs from entering the review flow

---

## 25. Human Oversight

Human oversight is mandatory throughout the intelligence layer.

### 25.1 Oversight Points

* **Context review.** Assembled context is presented before execution (WR-018).
* **Plan review.** Planned multi-step work is visible before execution.
* **Draft review.** Drafts are reviewable, editable, and approvable (AIR-037).
* **Decision record.** Review decisions and approvals are preserved (WR-025, DR-019).
* **Configuration review.** Configuration changes remain reviewable and traceable (AIR-057).

### 25.2 Oversight Principles

* The researcher retains responsibility for factual accuracy, source relevance, academic integrity, and publication suitability (AIR-038).
* The system assists rather than automates academic judgment (AIR-003, AIR-044).
* Generated outputs remain distinguishable from user-authored content (AIR-006).

### 25.3 Interactions

* Human decisions enter the workflow through the Review Pipeline and Conversation Intelligence
* Oversight outcomes are recorded in the Memory Architecture and preserved for audit (AIR-054)

---

## 26. Logical Interactions Among Components

The following flow summarizes how the intelligence capabilities interact across a complete research cycle:

1. The researcher provides materials and requests (Conversation Intelligence).
2. The Knowledge Processing Pipeline transforms materials into knowledge and chunks.
3. The Memory Architecture captures project context and decisions.
4. The Planning Layer and Capability Orchestration select and sequence capabilities (renamed from "Agent Orchestration" by ADR-009).
5. The Retrieval Strategy and Context Assembly Pipeline gather evidence and build context.
6. Prompt Management and Context Window Management prepare the bounded request.
7. Provider Abstraction executes the request; Research Intelligence and the Writing Pipeline produce outcomes.
8. The Citation and Evidence Flow keeps every outcome traceable to source.
9. The Review Pipeline presents outcomes for human decision.
10. The Reflection Loop and Learning and Memory Preservation close the cycle by updating memory.

This loop repeats iteratively across sessions, preserving continuity and human oversight at every step.

---

## 27. Traceability to SRS

The intelligence architecture is traceable to the approved requirements as follows:

* AI philosophy and operating principles: AIR-001 to AIR-006.
* AI lifecycle and orchestration: AIR-004, AIR-005, AIR-063, AIR-064, WR-016 to WR-025.
* Knowledge processing and interpretation: AIR-007 to AIR-012, WR-007 to WR-009, MVP-005 to MVP-006, DR-007 to DR-009.
* Context construction and window management: AIR-013 to AIR-015, WR-016 to WR-018, MVP-013 to MVP-014.
* Memory architecture and learning: AIR-019 to AIR-021, AIR-065 to AIR-066, WR-013 to WR-015, MVP-011 to MVP-012, DR-013 to DR-015.
* Author profile integration: AIR-016 to AIR-018, WR-010 to WR-012, MVP-009 to MVP-010, DR-010 to DR-012.
* Retrieval, chunking, and evidence flow: AIR-022 to AIR-027, AIR-046 to AIR-048, AIR-067 to AIR-068, WR-017, MVP-007 to MVP-008, DR-006, DR-008, DR-018.
* Prompt management and explainability: AIR-028 to AIR-030, AIR-049 to AIR-051.
* Writing and refinement: AIR-031 to AIR-036, WR-019 to WR-021, MVP-015 to MVP-017, DR-016 to DR-018.
* Review, oversight, and human-in-the-loop: AIR-037 to AIR-039, WR-022 to WR-025, MVP-018 to MVP-020, DR-019.
* Traceability and audit: AIR-052 to AIR-054, NFR-040.
* Provider abstraction and configuration: AIR-040 to AIR-042, AIR-055 to AIR-057, API-029 to API-031, NFR-026, NFR-031 to NFR-032.
* Failure handling and safety: AIR-043 to AIR-045, NFR-003 to NFR-006, NFR-027 to NFR-028, WR-036.
* Extensibility: AIR-058 to AIR-060, NFR-015 to NFR-018.
* Research workflow alignment: WR-001 to WR-039, MVP-025 to MVP-026, RDM-001 to RDM-010.
* ADR traceability: ADR-001 (separation of concerns); ADR-002 (provider abstraction gateway); ADR-005 (retrieval and search strategy); ADR-006 (async pipeline coordination); ADR-009 (Agent workspace introduction; renames Agent Orchestration/Registry to Capability Orchestration/Registry, §13–§14).

These traceability links keep the intelligence architecture accountable to the approved product requirements rather than to implementation convenience.
