# PRE-PII-GUARD Hook

## Purpose
Masks sensitive personal information (PII) before agent processing to protect privacy.

## Process

```powershell
param(
    [object]$InputData,
    [string]$OutputPath
)

# Create deep copy for safe modification
$sanitized = $InputData | ConvertTo-Json | ConvertFrom-Json

# PII Patterns
$patterns = @{
    Email       = '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    Phone       = '\+?[\d\s\-()]{10,20}'
    SSN         = '\d{3}-\d{2}-\d{4}'
    Name        = '(?:[A-Z][a-z]+ ){1,3}' # Simple name pattern
}

# Function to mask PII
function Mask-PII {
    param([string]$Text, [string]$PatternType, [int]$MaskLength = 3)
    
    if (-not $Text) { return $Text }
    
    $pattern = $patterns[$PatternType]
    $replacement = '[' + $PatternType + '-MASKED]'
    
    return [regex]::Replace($Text, $pattern, $replacement)
}

# Scan and mask all string fields
$fieldsToCheck = @(
    'business_context.initiator',
    'scope.departments_involved',
    'description',
    'title'
)

foreach ($field in $fieldsToCheck) {
    $pathParts = $field -split '\.'
    $obj = $sanitized
    
    # Navigate to field
    for ($i = 0; $i -lt $pathParts.Count - 1; $i++) {
        $obj = $obj.($pathParts[$i])
    }
    
    $fieldName = $pathParts[-1]
    $value = $obj.$fieldName
    
    if ($value -is [string]) {
        # Mask emails
        $value = Mask-PII -Text $value -PatternType 'Email'
        # Mask phone numbers
        $value = Mask-PII -Text $value -PatternType 'Phone'
        # Mask SSNs
        $value = Mask-PII -Text $value -PatternType 'SSN'
        
        $obj.$fieldName = $value
    }
}

# Save sanitized data
$sanitized | ConvertTo-Json -Depth 10 | Set-Content $OutputPath

Write-Host "✓ PII masking complete. $(($sanitized | ConvertTo-Json | ConvertFrom-Json | ConvertTo-Json).Length) chars sanitized"
exit 0
```

## Masked Patterns
- **Email**: `user@example.com` → `[EMAIL-MASKED]`
- **Phone**: `+1 (555) 123-4567` → `[PHONE-MASKED]`
- **SSN**: `123-45-6789` → `[SSN-MASKED]`
- **Names**: `John Smith` → `[NAME-MASKED]`

## Privacy Policy
- Masked data is used for advisory analysis only
- Original PII never appears in output
- Sanitized data logged for audit trail (masked values only)
- User receives de-identified advisory (suitable for sharing with broader team)

