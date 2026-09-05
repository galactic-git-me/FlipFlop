Set-Location 'C:\Users\mclar\CODING\FlipFlop\flipflop-api'
while ($true) {
  "$(Get-Date -Format o) [watchdog] starting uvicorn..." | Out-File -FilePath 'C:\Users\mclar\CODING\FlipFlop\logs\gemradar-api.log' -Append -Encoding utf8
  & python -m uvicorn app.main:app --host 0.0.0.0 --port 18000 --log-level info *>> 'C:\Users\mclar\CODING\FlipFlop\logs\gemradar-api.log'
  "$(Get-Date -Format o) [watchdog] uvicorn exited (code $LASTEXITCODE) - restarting in 5s..." | Out-File -FilePath 'C:\Users\mclar\CODING\FlipFlop\logs\gemradar-api.log' -Append -Encoding utf8
  Start-Sleep -Seconds 5
}
