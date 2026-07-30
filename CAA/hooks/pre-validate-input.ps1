# PRE-VALIDATE-INPUT Hook

## Purpose
Validates the input JSON against schemas/input.schema.json before processing.

## Process

```powershell
param(
    [string]$InputJsonPath,
    [string]$SchemaPath
)

# Load input JSON
try {
    $inputData = Get-Content $InputJsonPath | ConvertFrom-Json
    Write-Host "✓ Input JSON parsed successfully"
} catch {
    Write-Error "Input JSON is not valid JSON format: $_"
    exit 1
}

# Load schema
$schema = Get-Content $SchemaPath | ConvertFrom-Json

# Validate required fields
$requiredFields = $schema.required
foreach ($field in $requiredFields) {
    if (-not $inputData.PSObject.Properties[$field]) {
        Write-Error "Required field missing: $field"
        exit 1
    }
}

Write-Host "✓ All required fields present"

# Validate field types (basic)
if ($inputData.change_id -isnot [string]) {
    Write-Error "change_id must be a string"
    exit 1
}

if ($inputData.title -isnot [string] -or $inputData.title.Length -gt 100) {
    Write-Error "title must be a string (max 100 chars)"
    exit 1
}

Write-Host "✓ Input validation passed"
exit 0
```

## Success Criteria
- ✅ Input is valid JSON
- ✅ All required fields present (change_id, title, description, business_context)
- ✅ Field types match schema expectations
- ✅ No blocking validation errors

## Failure Handling
If validation fails:
- Write detailed error message
- Exit with code 1 (stops pipeline)
- Report validation errors to user before agent runs

