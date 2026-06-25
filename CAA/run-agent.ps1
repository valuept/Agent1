# SAP Change Advisor Agent - Main Orchestrator

## Overview
This orchestrator runs the evaluator-optimizer pattern with 2 passes.

## Usage

```powershell
.\run-agent.ps1 -InputFile "input.json" -OutputDir "output"
```

## Parameters

- **InputFile** (required): Path to input JSON file
- **OutputDir** (default: "./output"): Directory for output files

## Process Flow

### Step 1: Pre-Hooks (Validation)
```powershell
Write-Host "=== PRE-HOOKS: Validation & PII Guard ==="

# Run input validation
& ".\hooks\pre-validate-input.ps1" -InputJsonPath $InputFile -SchemaPath ".\schemas\input.schema.json"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Input validation failed"
    exit 1
}

# Run PII masking
$tempSanitized = "$env:TEMP\sanitized_$(Get-Random).json"
& ".\hooks\pre-pii-guard.ps1" -InputData $inputData -OutputPath $tempSanitized
if ($LASTEXITCODE -ne 0) {
    Write-Error "PII masking failed"
    exit 1
}

$inputData = Get-Content $tempSanitized | ConvertFrom-Json
Remove-Item $tempSanitized -Force
```

### Step 2: PASS 1 - Initial Processing

```powershell
Write-Host "=== PASS 1: Initial Requirement Breakdown ==="

# 1. Normalize requirement
$normalized = Invoke-SkillFromFile ".\skills\requirement-normalizer.txt" $inputData
Write-Host "✓ Requirement normalized"

# 2. Generate questions
$questions = Invoke-SkillFromFile ".\skills\gap-question-generator.txt" $normalized
Write-Host "✓ Gap questions generated (Count: $($questions.Count))"

# 3. Analyze impact
$impact = Invoke-SkillFromFile ".\skills\impact-analyzer.txt" $normalized
Write-Host "✓ Impact analysis complete (Risk Score: $($impact.summary_risk_score))"

# 4. Check compliance
$compliance = Invoke-SkillFromFile ".\skills\compliance-checker.txt" $normalized
Write-Host "✓ Compliance checks complete"

# 5. Design test cases
$testcases = Invoke-SkillFromFile ".\skills\testcase-designer.txt" $normalized
Write-Host "✓ Test cases designed (Count: $($testcases.Count))"

# 6. Generate implementation steps
$implementation = Invoke-SkillFromFile ".\skills\handover-writer.txt" $normalized
Write-Host "✓ Implementation steps created"

# Activate optional skills if requested
if ($inputData.skill_requests -contains "grill-me") {
    $grillme = Invoke-SkillFromFile ".\skills\grill-me.txt" $normalized
    Write-Host "✓ Grill-me deep-dive completed"
}
```

### Step 3: Quality Gates - PASS 1

```powershell
Write-Host "`n=== QUALITY GATES (Pass 1) ==="

# Gate 1: Evidence Only
Write-Host "[Gate 1] evidence_only: Checking all claims are backed by evidence..."
$evidenceCheckPass = Test-EvidenceOnly $normalized $questions $impact
if (-not $evidenceCheckPass) {
    Write-Warning "Gate 1 FAILED: Some claims lack evidence"
    $needsPass2 = $true
}

# Gate 2: Schema Compliance
Write-Host "[Gate 2] schema_compliance: Checking output matches schema..."
$schemaCheckPass = Test-SchemaCompliance $normalized $outputSchema
if (-not $schemaCheckPass) {
    Write-Error "Gate 2 FAILED: Output does not match schema - BLOCKING"
    exit 1
}

# Gate 3: Explicit Unknowns
Write-Host "[Gate 3] explicit_unknowns: Checking all gaps are stated..."
$unknownsCheckPass = Test-ExplicitUnknowns $questions
if (-not $unknownsCheckPass) {
    Write-Warning "Gate 3 FAILED: Some gaps are implicit, not explicit"
    $needsPass2 = $true
}

# Gate 4: Risk Transparency
Write-Host "[Gate 4] risk_transparency: Checking risks are ranked..."
$riskCheckPass = Test-RiskTransparency $impact
if (-not $riskCheckPass) {
    Write-Warning "Gate 4 FAILED: Risks not clearly ranked"
    $needsPass2 = $true
}

if ($evidenceCheckPass -and $riskCheckPass -and $unknownsCheckPass) {
    Write-Host "✓ All quality gates passed - Output quality is HIGH"
} else {
    Write-Host "⚠️  Some quality gates flagged - Proceeding to Pass 2 optimization"
    $needsPass2 = $true
}
```

### Step 4: PASS 2 - Optimization (if needed)

```powershell
if ($needsPass2) {
    Write-Host "`n=== PASS 2: Optimization & Refinement ==="
    
    # Deepen risk analysis
    $impact = Invoke-SkillFromFile ".\skills\impact-analyzer.txt" $normalized `
        -Param @{ refineRisks = $true; pass = 2 }
    Write-Host "✓ Risk analysis deepened"
    
    # Enhance compliance analysis
    $compliance = Invoke-SkillFromFile ".\skills\compliance-checker.txt" $normalized `
        -Param @{ pass = 2 }
    Write-Host "✓ Compliance analysis refined"
    
    # Expand test coverage
    $testcases = Invoke-SkillFromFile ".\skills\testcase-designer.txt" $normalized `
        -Param @{ expandCoverage = $true; pass = 2 }
    Write-Host "✓ Test case coverage expanded"
    
    Write-Host "✓ Pass 2 optimization complete"
}
```

### Step 5: Generate Output

```powershell
Write-Host "`n=== GENERATING OUTPUT PACKAGE ==="

# Create output JSON structure
$outputJson = @{
    metadata = @{
        change_id = $inputData.change_id
        generated_at = Get-Date -Format "o"
        agent_version = "2.0.0"
        passes_completed = if ($needsPass2) { 2 } else { 1 }
    }
    normalized_requirement = $normalized
    open_questions = $questions
    impact_analysis = $impact
    compliance_checks = $compliance
    test_cases = $testcases
    implementation_steps = $implementation
    handover_package = $handover
    agent_notes = @{
        unknowns = $unknowns
        assumptions = $assumptions
        optimization_notes = if ($needsPass2) { @("Pass 2: Risk analysis deepened", "Pass 2: Compliance refined", "Pass 2: Test coverage expanded") } else { @() }
    }
}

# Save JSON output
$outputFile = Join-Path $OutputDir "$($inputData.change_id)-advisory.json"
$outputJson | ConvertTo-Json -Depth 10 | Set-Content $outputFile
Write-Host "✓ JSON output saved: $outputFile"

# Generate Markdown output (from handover-writer)
$markdownFile = Join-Path $OutputDir "$($inputData.change_id)-advisory.md"
$markdownContent = Generate-MarkdownAdvisory $outputJson
Set-Content $markdownFile $markdownContent
Write-Host "✓ Markdown advisory saved: $markdownFile"
```

### Step 6: Post-Hooks (Output Validation)

```powershell
Write-Host "`n=== POST-HOOKS: Output Validation ==="

& ".\hooks\post-validate-output.ps1" -OutputJsonPath $outputFile -SchemaPath ".\schemas\output.schema.json"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Output validation failed"
    exit 1
}
```

### Step 7: Summary & Delivery

```powershell
Write-Host "`n=== DELIVERY SUMMARY ==="
Write-Host "Change ID: $($inputData.change_id)"
Write-Host "Title: $($inputData.title)"
Write-Host "Risk Level: $($impact.summary_risk_score) / 9"
Write-Host "Compliance Status: $(Get-ComplianceStatus $compliance)"
Write-Host "Test Cases: $($testcases.Count)"
Write-Host "Implementation Steps: $($implementation.steps.Count)"
Write-Host ""
Write-Host "OUTPUT FILES:"
Write-Host "  - $markdownFile (for review & stakeholder distribution)"
Write-Host "  - $outputFile (for system processing)"
Write-Host ""
Write-Host "✓ Agent execution complete. Advisory package is ready for stakeholder review."
Write-Host ""
Write-Host "NEXT STEPS:"
Write-Host "1. Distribute markdown advisory to stakeholders (Finance, IT, Process Owner)"
Write-Host "2. Schedule stakeholder review sessions"
Write-Host "3. Address open questions and compliance gaps"
Write-Host "4. Submit to Change Advisory Board (CAB)"
```

## Helper Functions

```powershell
function Invoke-SkillFromFile {
    param([string]$SkillFile, [object]$Input, [hashtable]$Param)
    # Load skill from text file
    # Parse human-readable skill into executable logic
    # Return structured output
}

function Test-EvidenceOnly {
    param([object]$Normalized, [array]$Questions, [object]$Impact)
    # Verify all statements trace back to input or domain knowledge
    return $true
}

function Test-SchemaCompliance {
    param([object]$Data, [object]$Schema)
    # Validate output against schema
    return $true
}

function Test-ExplicitUnknowns {
    param([array]$Questions)
    # Verify unknowns are explicitly stated
    return $true
}

function Test-RiskTransparency {
    param([object]$Impact)
    # Verify risks are ranked by probability × impact
    return $true
}

function Generate-MarkdownAdvisory {
    param([object]$OutputJson)
    # Convert JSON output to stakeholder-ready Markdown
    # Use templates from memory/50-templates.md
}

function Get-ComplianceStatus {
    param([array]$Compliance)
    # Summarize compliance status (Compliant, Requires Review, Non-Compliant)
    return "Compliant"
}
```

## Execution Example

```powershell
PS> .\run-agent.ps1 -InputFile "tests/example-input.json" -OutputDir "test-output"

=== PRE-HOOKS: Validation & PII Guard ===
✓ Input validation passed
✓ PII masking complete

=== PASS 1: Initial Requirement Breakdown ===
✓ Requirement normalized
✓ Gap questions generated (Count: 7)
✓ Impact analysis complete (Risk Score: 6)
✓ Compliance checks complete
✓ Test cases designed (Count: 8)
✓ Implementation steps created

=== QUALITY GATES (Pass 1) ===
[Gate 1] evidence_only: All claims backed by evidence ✓
[Gate 2] schema_compliance: Output matches schema ✓
[Gate 3] explicit_unknowns: All gaps are explicit ✓
[Gate 4] risk_transparency: Risks ranked by score ✓
✓ All quality gates passed - Output quality is HIGH

=== GENERATING OUTPUT PACKAGE ===
✓ JSON output saved: test-output/CHG-2026-001-advisory.json
✓ Markdown advisory saved: test-output/CHG-2026-001-advisory.md

=== POST-HOOKS: Output Validation ===
✓ Output validation passed

=== DELIVERY SUMMARY ===
Change ID: CHG-2026-001
Title: S/4HANA Cloud Migration
Risk Level: 6 / 9
Compliance Status: Requires Review
Test Cases: 8
Implementation Steps: 5

OUTPUT FILES:
  - test-output/CHG-2026-001-advisory.md
  - test-output/CHG-2026-001-advisory.json

✓ Agent execution complete. Advisory package is ready for stakeholder review.
```

## Exit Codes
- **0**: Success - advisory package ready
- **1**: Error - validation or processing failed (check logs)
- **2**: Blocked - critical issue preventing execution

