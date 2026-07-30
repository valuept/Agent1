param(
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

if (-not (Test-Path -LiteralPath $OutputPath)) {
    throw "Output file not found: $OutputPath"
}

$raw = Get-Content -LiteralPath $OutputPath -Raw
$obj = $null
try {
    $obj = $raw | ConvertFrom-Json -ErrorAction Stop
} catch {
    throw "Output must be valid JSON. Details: $($_.Exception.Message)"
}

$required = @(
    "summary",
    "open_questions",
    "risks",
    "implementation_steps",
    "test_cases",
    "handover_note",
    "approval_note"
)

foreach ($key in $required) {
    if (-not $obj.PSObject.Properties.Name.Contains($key)) {
        throw "Missing required output field: $key"
    }
}

if ($obj.risks.Count -lt 1) {
    throw "Output must include at least one risk item."
}

if ($obj.test_cases.Count -lt 3) {
    throw "Output must include at least three test cases."
}

Write-Output "post-validate-output: OK"
