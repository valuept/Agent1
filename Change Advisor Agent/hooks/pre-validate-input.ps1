param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath
)

if (-not (Test-Path -LiteralPath $InputPath)) {
    throw "Input file not found: $InputPath"
}

$raw = Get-Content -LiteralPath $InputPath -Raw
if ([string]::IsNullOrWhiteSpace($raw)) {
    throw "Input file is empty."
}

$obj = $null
try {
    $obj = $raw | ConvertFrom-Json -ErrorAction Stop
} catch {
    throw "Input must be valid JSON. Details: $($_.Exception.Message)"
}

$required = @("change_request", "project_context", "constraints")
foreach ($key in $required) {
    if (-not $obj.PSObject.Properties.Name.Contains($key)) {
        throw "Missing required field: $key"
    }
}

if ($obj.constraints.Count -lt 1) {
    throw "constraints must contain at least one item."
}

Write-Output "pre-validate-input: OK"
