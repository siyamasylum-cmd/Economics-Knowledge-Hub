$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$TaskName = "BEPI Daily Pipeline"
$ScriptPath = Join-Path $ProjectRoot "run_daily_pipeline.bat"

$Action = New-ScheduledTaskAction -Execute $ScriptPath -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At 7:00AM
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Collect, analyze, score, and store BEPI history every morning." `
    -Force

Write-Host "Scheduled '$TaskName' to run daily at 7:00 AM."
Write-Host "Pipeline logs will be written to logs\daily_pipeline.log."
