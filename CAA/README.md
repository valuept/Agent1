# SAP-Consulting-Change-Advisor Agent v2.0.0

## Purpose

This agent transforms raw change requests into **review-ready advisory packages** containing:
- ✅ Structured, normalized requirements
- ❓ Open questions (critical, high, medium, low)
- ⚠️ Impact analysis with risk matrix
- 🔒 Compliance checks against governance frameworks
- 🧪 Test case design with acceptance criteria
- 📋 Implementation steps with rollback plans
- 📦 Handover package ready for stakeholder review

## Quick Start

### 1. Prepare Input
Create a JSON file following `schemas/input.schema.json`:

```json
{
  "change_id": "CHG-2026-001",
  "title": "Migrate to S/4HANA Cloud",
  "description": "Move from SAP on-premise to cloud instance",
  "business_context": {
    "initiator": "CTO",
    "business_drivers": ["Reduce infrastructure costs", "Improve scalability"],
    "target_date": "2026-12-31"
  },
  "scope": {
    "systems_affected": ["ERP", "FI", "MM"],
    "departments_involved": ["Finance", "Supply Chain"]
  }
}
```

### 2. Run the Agent

```powershell
# From CAA directory
.\run-agent.ps1 -InputFile "path/to/input.json" -OutputDir "output"
```

### 3. Review Output

Check `output/<change_id>-advisory.md` for:
- Executive summary
- Normalized requirements
- 5-7 strategic questions for stakeholders
- Risk assessment
- Compliance verdict
- Test strategy
- Implementation roadmap

## Architecture

### Pipeline Pattern: Evaluator-Optimizer

```
Input JSON
    ↓
[PRE-HOOKS: Validation + PII Guard]
    ↓
PASS 1:
  • requirement-normalizer → structured requirement
  • gap-question-generator → 5-7 open questions
  • impact-analyzer → risk matrix
  • compliance-checker → compliance verdict
  • testcase-designer → test cases
  • handover-writer → output structure
    ↓
QUALITY GATES:
  ✓ evidence_only: only factual claims
  ✓ schema_compliance: output matches schema
  ✓ explicit_unknowns: all gaps stated
  ✓ risk_transparency: risks clearly ranked
    ↓
PASS 2 (if needed):
  • Refine based on gate feedback
  • Deepen risk mitigation strategies
  • Clarify compliance requirements
    ↓
[POST-HOOKS: Output Validation]
    ↓
Output JSON + Markdown Advisory
```

### Directory Structure

```
CAA/
├── run-agent.ps1              # Main orchestrator
├── config.yaml                # Agent configuration
├── README.md                  # This file
│
├── schemas/
│   ├── input.schema.json      # Input structure
│   └── output.schema.json     # Output structure
│
├── skills/
│   ├── requirement-normalizer.txt
│   ├── gap-question-generator.txt
│   ├── impact-analyzer.txt
│   ├── compliance-checker.txt
│   ├── testcase-designer.txt
│   ├── handover-writer.txt
│   └── grill-me.txt (optional)
│
├── memory/
│   ├── 00-governance.md       # SAP governance policies
│   ├── 10-project-context.md  # Project context template
│   ├── 20-domain-knowledge.md # SAP domain expertise
│   ├── 30-architecture-decisions.md
│   ├── 50-templates.md        # Output templates
│   ├── 60-cases/              # Case studies (write target)
│   └── 70-retrospectives/     # Retrospectives (write target)
│
├── hooks/
│   ├── pre-validate-input.ps1
│   ├── pre-pii-guard.ps1
│   └── post-validate-output.ps1
│
├── artifacts/
│   └── leanix-export-preparation.txt (optional)
│
└── tests/
    ├── test-scenarios.md
    ├── example-input.json
    └── expected-output.md
```

## Skills Explained

| Skill | Purpose | Output |
|-------|---------|--------|
| **requirement-normalizer** | Validates & structures raw input | Normalized requirement object |
| **gap-question-generator** | Identifies critical unknowns | 5-7 open questions with priority |
| **impact-analyzer** | Assesses change impact | Risk matrix with scores |
| **compliance-checker** | Validates against SAP governance | Compliance verdict |
| **testcase-designer** | Creates test cases | Test cases with acceptance criteria |
| **handover-writer** | Packages for stakeholder review | Executive summary + advisory |
| **grill-me** (optional) | Deep-dive Q&A for requirements | Extended clarification |

## Configuration

Edit `config.yaml` to:
- Adjust pipeline sequence
- Enable/disable skills
- Change optimization passes (max_passes: 2)
- Update memory sources
- Modify output gates

## Human-in-the-Loop Interaction

The agent supports interactive feedback at key points:
- After Pass 1: Review questions for stakeholder input
- Risk assessment: Confirm risk severity
- Compliance check: Discuss non-compliant items
- Test design: Validate test approach

Marks for interaction: `[HUMAN DECISION REQUIRED]` in output

## Output Quality Gates

All output passes these 4 quality gates:

1. **evidence_only**: Claims backed by requirement or domain knowledge
2. **schema_compliance**: Output structure matches `schemas/output.schema.json`
3. **explicit_unknowns**: All gaps explicitly stated
4. **risk_transparency**: Risks ranked by probability × impact

## Optional Features

### grill-me Skill
Activate for deeper requirements analysis:
```json
{
  "skill_requests": ["grill-me"]
}
```

### LeanIX Export
Prepare for LeanIX integration:
```json
{
  "leanix_export": {
    "enabled": true,
    "application_id": "SAP_CHANGE_123"
  }
}
```

## Testing the Agent

Run test scenarios:
```powershell
.\run-agent.ps1 -InputFile "tests/example-input.json" -OutputDir "test-output"
```

Compare with expected output in `tests/expected-output.md`

## Security & Privacy

**Pre-hooks ensure:**
- ✅ PII masking (email, phone, names)
- ✅ Sensitive data redaction
- ✅ Input validation against schema

**Post-hooks ensure:**
- ✅ Output structure compliance
- ✅ No sensitive data leakage
- ✅ Complete metadata

## Troubleshooting

| Issue | Solution |
|-------|----------|
| JSON validation fails | Check `schemas/input.schema.json` |
| Missing questions | Increase gap-question-generator depth |
| Risk not ranked | Review impact-analyzer memory context |
| Compliance checks incomplete | Verify `20-domain-knowledge.md` is complete |

## Maintenance

- Update `memory/` files quarterly with new SAP best practices
- Add case studies to `memory/60-cases/` after each major change
- Review optimization notes in Pass 2 feedback
- Archive completed advisory packages to `memory/70-retrospectives/`

## Version History

- **v2.0.0** (current): Evaluator-Optimizer pattern, 4 quality gates, 6 core skills + optional modules
- **v1.0.0**: Initial framework

---

**Agent Version:** 2.0.0  
**Last Updated:** 2026-06-11  
**Status:** ✅ Production Ready
