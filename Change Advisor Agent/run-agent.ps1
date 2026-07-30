param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,
    [string]$AgentRoot = ".",
    [string]$MemoryRoot = ".\\memory",
    [string]$BundleOutPath = ".\\artifacts\\context-bundle.txt"
)

$ErrorActionPreference = "Stop"

$preValidate = Join-Path $AgentRoot "hooks\\pre-validate-input.ps1"
$prePii = Join-Path $AgentRoot "hooks\\pre-pii-guard.ps1"
$systemPromptPath = Join-Path $AgentRoot "prompts\\system.txt"

& $preValidate -InputPath $InputPath
& $prePii -InputPath $InputPath

if (-not (Test-Path -LiteralPath $systemPromptPath)) {
    throw "System prompt not found: $systemPromptPath"
}

$dirs = @(
    "00-governance",
    "10-project-context",
    "20-domain-knowledge",
    "30-architecture-decisions",
    "50-templates"
)

$contextParts = New-Object System.Collections.Generic.List[string]
foreach ($dir in $dirs) {
    $full = Join-Path $MemoryRoot $dir
    if (Test-Path -LiteralPath $full) {
        $files = Get-ChildItem -LiteralPath $full -File -Recurse | Select-Object -First 6
        foreach ($f in $files) {
            $content = Get-Content -LiteralPath $f.FullName -Raw
            $contextParts.Add("## MEMORY: $($f.FullName)`r`n$content`r`n")
        }
    }
}

$systemPrompt = Get-Content -LiteralPath $systemPromptPath -Raw
$inputJson = Get-Content -LiteralPath $InputPath -Raw
$outputSchema = Get-Content -LiteralPath (Join-Path $AgentRoot "schemas\\output.schema.json") -Raw

$bundle = @"
# CHANGE ADVISOR CONTEXT BUNDLE

## SYSTEM INSTRUCTION
$systemPrompt

## INPUT JSON
$inputJson

## REQUIRED OUTPUT SCHEMA
$outputSchema

## ORDERED MEMORY CONTEXT
$($contextParts -join "`r`n")
"@

$outDir = Split-Path -Parent $BundleOutPath
if (-not (Test-Path -LiteralPath $outDir)) {
    New-Item -Path $outDir -ItemType Directory | Out-Null
}

Set-Content -LiteralPath $BundleOutPath -Value $bundle -Encoding UTF8
Write-Output "Context bundle written to: $BundleOutPath"
Write-Output "Next step: paste this bundle into Copilot Desktop for execution."
