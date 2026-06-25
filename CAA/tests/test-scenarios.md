# Test Scenarios for SAP Change Advisor Agent

## Overview
These test scenarios validate the agent's functionality across different change complexity levels.

## Test Scenario 1: Simple Configuration Change (LOW COMPLEXITY)

**Input**: Simple SAP FI configuration
**Expected Output**: 
- 1-2 open questions
- 3-4 risks (mostly LOW)
- 1-2 compliance checks
- 3-4 test cases
- 2-3 implementation steps

**Success Criteria**:
- ✅ Agent completes in Pass 1 (no Pass 2 needed)
- ✅ Risk score 2-3 (LOW risk)
- ✅ All gates pass on first attempt
- ✅ Test cases practical and specific

---

## Test Scenario 2: Module Integration (MEDIUM COMPLEXITY)

**Input**: Purchase Order to Accounts Payable integration
**Expected Output**:
- 5-6 open questions
- 6-8 risks (mix of MEDIUM and some HIGH)
- 3-4 compliance checks
- 6-8 test cases
- 4-6 implementation steps

**Success Criteria**:
- ✅ Agent may need Pass 2 for optimization
- ✅ Risk score 4-6 (MEDIUM risk)
- ✅ Questions target root causes, not symptoms
- ✅ Compliance checks cover integration patterns

---

## Test Scenario 3: Cloud Migration (HIGH COMPLEXITY)

**Input**: Complete S/4HANA cloud migration
**Expected Output**:
- 7+ open questions
- 8+ risks (multiple HIGH/CRITICAL)
- 5+ compliance checks
- 8+ test cases
- 6+ implementation steps
- Optional: grill-me deep-dive for stakeholder alignment

**Success Criteria**:
- ✅ Agent triggers Pass 2 for refinement
- ✅ Risk score 6-9 (HIGH risk)
- ✅ Compliance gaps explicitly flagged
- ✅ Comprehensive test strategy
- ✅ Detailed implementation roadmap with contingencies

---

## Test Scenario 4: Edge Case - Ambiguous Requirements

**Input**: Vague requirement with conflicting scope
**Expected Output**:
- 8+ open questions (many CRITICAL priority)
- Clear scope clarification recommendations
- NO-GO or CONDITIONAL recommendation

**Success Criteria**:
- ✅ Agent surfaces all ambiguities
- ✅ Questions are actionable for stakeholder clarification
- ✅ No assumptions made - all gaps explicitly stated

---

## Test Scenario 5: Optional Skills Activation

**Input**: Complex change with "grill-me" skill requested
**Expected Output**:
- Standard advisory output (Scenarios 2-3 level)
- PLUS: Deep-dive Q&A findings
- PLUS: Stakeholder alignment assessment
- PLUS: Hidden assumptions surfaced

**Success Criteria**:
- ✅ Optional skill activates only when requested
- ✅ Deep-dive findings enhance primary advisory
- ✅ Specific follow-up actions recommended

---

## Execution Schedule

| Scenario | Purpose | Effort | Est. Duration |
|----------|---------|--------|---------------|
| Scenario 1 | Validate basic functionality | 30 min | 5-10 sec agent run |
| Scenario 2 | Validate medium complexity | 45 min | 10-15 sec agent run |
| Scenario 3 | Validate high complexity | 60 min | 20-30 sec agent run |
| Scenario 4 | Validate edge cases | 30 min | 10-15 sec agent run |
| Scenario 5 | Validate optional skills | 30 min | 10-15 sec agent run |

**Total Test Effort**: ~3 hours (setup + execution + validation)

---

## Pass/Fail Criteria

**PASS if:**
- ✅ Agent completes without errors
- ✅ Output matches expected complexity level
- ✅ All quality gates pass
- ✅ Risk scores reasonable for scenario
- ✅ Compliance checks appropriate to domain
- ✅ Test cases cover acceptance criteria
- ✅ Implementation steps are logical and sequenced

**FAIL if:**
- ❌ Agent crashes or exits with error
- ❌ Output missing required fields
- ❌ Risk scores unrealistic (e.g., score 1 for major cloud migration)
- ❌ Open questions vague or unanswerable
- ❌ Test cases don't match requirement
- ❌ Compliance checks inapplicable or incomplete

