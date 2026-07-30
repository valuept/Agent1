# SAP Change Advisor Agent — Version History

## Overview

This document compares **V1** and **V2** of the SAP Change Advisor Agent, highlighting architectural improvements, new capabilities, and migration notes.

---

## Version 1.0 (Baseline)

### Core Purpose
- Transform raw change requests into structured advisory packages
- Provide risk assessment, open questions, and implementation guidance
- Deterministic input/output contracts
- Hook-based validation gating

### Architecture
- **Mode**: Human-in-the-loop
- **Orchestrator**: PowerShell (`run-agent.ps1`)
- **Pattern**: Linear pipeline with pre/post hooks

### Key Features
- **Input Schema**: Structured JSON with change metadata
- **Output Schema**: Risk-scored assessments, questions, implementation steps, test cases
- **Hooks**: Pre-validation (input format, PII guard) and post-validation (output schema compliance)
- **Memory Structure**: Project-specific folders for context engineering
  - `00-governance`
  - `10-project-context`
  - `20-domain-knowledge`
  - `30-architecture-decisions`
  - `50-templates`
- **Pipeline Stages**:
  - Requirement normalization
  - Gap question generation
  - Impact analysis
  - (Basic) compliance checking
  - Test case design
  - Handover document creation

### Context Engineering
- Ordered sources: governance → project → domain → architecture → templates
- Glob-based file inclusion (*.md, *.txt)
- Max 30 files per context bundle

### Output Artifacts
- `context-bundle.txt` — Combined context for LLM
- Model JSON output (validated against schema)
- Optional: Case logs and retrospectives

### Limitations
- No built-in support for extended skills (e.g., questioning modes)
- Compliance checks limited to technical aspects
- No modular / extensible compliance framework
- No structured business/domain compliance assessment
- No export preparation for downstream systems (e.g., LeanIX)
- Single-pass evaluation (no optimizer loop)

---

## Version 2.0 (Current)

### Core Purpose
- All V1 features **preserved**
- Add disciplined extensibility for modern agent workflows
- Strengthen compliance and questioning capabilities
- Enable downstream integrations

### Architecture
- **Mode**: Human-in-the-loop (unchanged)
- **Orchestrator**: PowerShell (unchanged)
- **Pattern**: **Evaluator-Optimizer** (new)

### New Features

#### 1. **Evaluator-Optimizer Protocol**
```yaml
evaluator_optimizer:
  enabled: true
  max_passes: 2
  gates:
    - evidence_only       # No invented facts
    - schema_compliance   # Output structure valid
    - explicit_unknowns   # Open questions surfaced
    - risk_transparency   # Risk scoring justified
```
- Two-pass design ensures output quality
- First pass: generate advisory; second pass: validate and refine
- Guards against hallucinations and incomplete reasoning

#### 2. **Expanded Compliance Model**
Output now includes:
```json
{
  "compliance_assessment": {
    "technical_compliance": {
      "items": [...]
    },
    "business_domain_compliance": {
      "items": [...]
    }
  }
}
```
- **Technical compliance**: Architecture, security, performance, ABAP Cloud readiness, etc.
- **Business/domain compliance**: HCM business rules, regulatory requirements, organizational standards, SAP best practices

#### 3. **Modular Skills Framework**
Skills are now first-class, composable units:
```yaml
skills:
  - id: requirement-normalizer
  - id: gap-question-generator
  - id: impact-analyzer
  - id: compliance-checker
  - id: testcase-designer
  - id: handover-writer
  - id: grill-me  # NEW
```

#### 4. **`/grill-me` Skill**
- Activated via input: `skill_requests: ["/grill-me"]`
- Purpose: Generate **probing questions only** (no recommendations)
- Use case: Discovery, requirement validation, devil's advocate role
- Output: `grill_me_questions` field in response
- Does **not** block main analysis

#### 5. **Optional LeanIX Export Module**
```yaml
optional_modules:
  - id: leanix-export-preparation
    activation:
      input_field: leanix_export.enabled
      equals: true
    artifact_path: artifacts/leanix-export-preparation.txt
```
- Input control: `leanix_export.enabled: true` and optional `scope_hint`
- Behavior: Conservative and evidence-bound
  - Maps findings to LeanIX application/capability model (if context provided)
  - Emits placeholders and open questions for unmapped items (no invented mappings)
- Output: Separate artifact file for manual review and handoff
- Intentionally **not core** — can be toggled off or replaced

#### 6. **Input Extensions**
New optional fields in input schema:
```json
{
  "skill_requests": ["/grill-me"],
  "leanix_export": {
    "enabled": true,
    "scope_hint": "Map SAP FI changes to GL and AP modules"
  }
}
```

#### 7. **Output Extensions**
Main output schema now supports:
```json
{
  "compliance_assessment": {...},
  "grill_me_questions": [...],
  "leanix_export_preparation": "..."  // emitted as separate file
}
```

### Context Engineering (Enhanced)
- Same ordered sources as V1
- Now supports **evidence-bound** mode: agent must cite context or explicitly mark as "unknown"
- Prevents agent from inventing facts missing from context

### Memory Structure (Extended)
Added write targets for continuous learning:
- `memory/60-cases` — Successful case summaries
- `memory/70-retrospectives` — Lessons learned and process improvements

### Backward Compatibility
- ✅ V1 input/output contracts fully respected
- ✅ V1 hooks (pre/post validation) still active
- ✅ V1 memory structure still used
- ✅ V1 pipeline stages unchanged
- ⚠️ New fields are optional; V1 inputs work as-is

---

## Migration & Usage

### Running V1-style (unchanged)
```powershell
.\run-agent.ps1 -InputPath .\examples\sample-input.json `
  -AgentRoot . -MemoryRoot .\memory `
  -BundleOutPath .\artifacts\context-bundle.txt
```
- Produces same output as V1
- No new compliance fields unless context hints them

### Using V2 New Features

#### Enable `/grill-me` skill
```json
{
  "project_name": "HCM Overtime Module",
  "change_title": "...",
  "skill_requests": ["/grill-me"]
}
```
- Adds `grill_me_questions` to output

#### Enable LeanIX export prep
```json
{
  "project_name": "...",
  "change_title": "...",
  "leanix_export": {
    "enabled": true,
    "scope_hint": "Map to Talent Management and Compensation modules"
  }
}
```
- Generates `artifacts/leanix-export-preparation.txt`
- Maps findings to LeanIX if context supports it; otherwise, open questions

#### Combined: Full V2 capabilities
```json
{
  "project_name": "Global Payroll Update",
  "change_title": "...",
  "skill_requests": ["/grill-me"],
  "leanix_export": {
    "enabled": true,
    "scope_hint": "PE, EMEA payroll ops"
  }
}
```
- Main output: full advisory + compliance + questions
- Side outputs: `/grill-me` questions + LeanIX prep

---

## Comparison Table

| Aspect | V1 | V2 |
|--------|----|----|
| **Pattern** | Linear | Evaluator-Optimizer |
| **Compliance** | Technical only | Technical + Business/Domain |
| **Extensible Skills** | Hardcoded | Modular, declarative |
| **Question Modes** | Part of main flow | `/grill-me` skill (optional) |
| **Export Prep** | None | LeanIX module (togglable) |
| **Evidence Binding** | Best-effort | Explicit gates + guards |
| **Backward Compat** | N/A | Full ✅ |

---

## Technical Files Changed

### New Files
- `skills/grill-me.txt` — Question generation skill
- `skills/leanix-export.txt` — (Optional) LeanIX mapping logic
- `artifacts/leanix-export-preparation.txt` — Output artifact (generated)

### Modified Files
- `agent.yaml` — Added evaluator-optimizer config, skills registry, optional modules
- `schemas/input.schema.json` — Added `skill_requests`, `leanix_export` fields
- `schemas/output.schema.json` — Added `compliance_assessment`, `grill_me_questions` fields
- `README.md` — Updated with V2 highlights and new input/output contract
- `run-agent.ps1` — (Internal) now passes optional module flags to LLM context
- `hooks/post-validate-output.ps1` — Enhanced to validate new output fields

### Unchanged (V1 compat guaranteed)
- `run-agent.ps1` — API and core logic stable
- `hooks/pre-validate-input.ps1`
- `hooks/pre-pii-guard.ps1`
- All core pipeline skills (V1 stages still run)
- Memory structure and context engineering core

---

## Deployment Notes

1. **No database or service changes** — purely prompt/schema evolution
2. **Hook system still gates output** — ensure post-validation is run
3. **Memory structure extended** — new write targets available but not required
4. **LeanIX module is optional** — disable by omitting `leanix_export.enabled` or setting to `false`
5. **Evaluator-optimizer can be tuned** — adjust `max_passes` and gates in `agent.yaml` if needed

---

## Future Roadmap

Potential V2.x enhancements:
- [ ] Live knowledge graph integration (LeanIX API)
- [ ] Multi-language requirement normalization
- [ ] Change CAB (Change Advisory Board) template generator
- [ ] Risk scoring ML model (currently rule-based)
- [ ] Integration with SAP Solution Manager or SAP Signavio
- [ ] Custom skill SDK for partner extensions

---

## Support & Questions

For V1 ↔ V2 migration or new feature adoption, refer to:
- **Input format**: `schemas/input.schema.json`
- **Output format**: `schemas/output.schema.json`
- **Example usage**: `examples/sample-input.json`
- **Agent config**: `agent.yaml`
- **Skill library**: `skills/` folder
