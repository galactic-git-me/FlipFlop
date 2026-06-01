# Run FlipFlop Locally With Docker

## 1) Start Chrome with remote debugging

Windows PowerShell:

```powershell
Stop-Process -Name chrome -Force -ErrorAction SilentlyContinue
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --user-data-dir="$env:TEMP\flipflop-chrome"
```

Keep this Chrome window open (solve any login/captcha prompts there).

## 2) Start the stack from project root

```bash
docker compose up --build
```

## 3) URLs

- Frontend: `http://localhost:4310`
- Backend: `http://localhost:4311`
- API base: `http://localhost:4311/api`

## 4) Stop

```bash
docker compose down
```

To also remove DB data:

```bash
docker compose down -v
```
