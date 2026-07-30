param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath
)

$raw = Get-Content -LiteralPath $InputPath -Raw

$patterns = @(
    "(?i)\\b\\d{11}\\b",
    "(?i)\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b",
    "(?i)\\b(iban|sozialversicherungsnummer|personalnummer)\\b"
)

foreach ($pattern in $patterns) {
    if ($raw -match $pattern) {
        throw "Potential sensitive data detected by PII guard pattern: $pattern"
    }
}

Write-Output "pre-pii-guard: OK"

