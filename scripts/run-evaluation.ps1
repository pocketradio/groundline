$ErrorActionPreference = "Stop"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PSScriptRoot "..\tmp\uv-python"
Set-Location (Join-Path $PSScriptRoot "..\backend")
uv run --python 3.12 python -m groundline.evaluation --output ..\evaluation_report.json
if ($LASTEXITCODE -ne 0) { throw "full evaluation failed with exit code $LASTEXITCODE" }
uv run --python 3.12 python -m groundline.evaluation --answers-only --output ..\evaluation_answers_report.json
if ($LASTEXITCODE -ne 0) { throw "answers-only evaluation failed with exit code $LASTEXITCODE" }
