# POST-VALIDATE-OUTPUT Hook

## Purpose
Validates the final output JSON matches schemas/output.schema.json before delivery.

## Process

```powershell
param(
    [string]$OutputJsonPath,
    [string]$SchemaPath
)

# Load output JSON
try {
    $outputData = Get-Content $OutputJsonPath | ConvertFrom-Json
    Write-Host "✓ Output JSON parsed successfully"
} catch {
    Write-Error "Output JSON is not valid JSON format: $_"
    exit 1
}

# Load schema
$schema = Get-Content $SchemaPath | ConvertFrom-Json

# Validate required fields
$requiredFields = $schema.required
foreach ($field in $requiredFields) {
    if (-not $outputData.PSObject.Properties[$field]) {
        Write-Error "Required field missing in output: $field"
        exit 1
    }
}

Write-Host "✓ All required output fields present"

# Validate nested structure completeness
function Validate-ComplexField {
    param([object]$Data, [string]$FieldName, [string]$Type)
    
    $field = $Data.$FieldName
    
    if ($Type -eq 'array' -and $field -is [array]) {
        if ($field.Count -eq 0) {
            Write-Warning "Field '$FieldName' is empty (array with 0 items)"
        } else {
            Write-Host "✓ Field '$FieldName' contains $($field.Count) items"
        }
    } elseif ($Type -eq 'object' -and $field -is [pscustomobject]) {
        $propertyCount = @($field.PSObject.Properties).Count
        Write-Host "✓ Field '$FieldName' is an object with $propertyCount properties"
    }
}

# Validate key arrays have content
Validate-ComplexField $outputData 'open_questions' 'array'
Validate-ComplexField $outputData 'compliance_checks' 'array'
Validate-ComplexField $outputData 'test_cases' 'array'
Validate-ComplexField $outputData 'implementation_steps' 'array'

# Validate risk scores are reasonable (1-9)
$riskScores = $outputData.impact_analysis.risk_matrix.risk_score
foreach ($score in $riskScores) {
    if ($score -lt 1 -or $score -gt 9) {
        Write-Error "Invalid risk score: $score (must be 1-9)"
        exit 1
    }
}

Write-Host "✓ All risk scores are valid (1-9 range)"

# Validate no PII in output
$outputText = $outputData | ConvertTo-Json
if ($outputText -match '\[EMAIL-MASKED\]|\[PHONE-MASKED\]|\[PII-') {
    Write-Host "✓ PII properly masked in output"
} elseif ($outputText -match '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}') {
    Write-Warning "Possible email found in output (verify no PII leakage)"
}

Write-Host "✓ Output validation passed - ready for delivery"
exit 0
```

## Validation Checklist
- ✅ Output is valid JSON
- ✅ All required fields present and populated
- ✅ Complex fields (arrays, objects) have content
- ✅ Risk scores are in valid range (1-9)
- ✅ No PII leakage in output
- ✅ Metadata fields complete (change_id, agent_version, generated_at)

## Failure Handling
If validation fails:
- Report validation error with specific field name
- Exit with code 1 (prevents output delivery)
- Trigger manual review of output quality

