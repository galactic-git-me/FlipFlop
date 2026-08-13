const { spawn } = require('child_process');

const proc = spawn(
  'C:/Users/mclar/CODING/flipflop/flipflop-api/.venv/Scripts/python.exe',
  ['-m', 'uvicorn', 'app.gem_radar_standalone:app', '--host', '127.0.0.1', '--port', '8500'],
  {
    cwd: __dirname,
    stdio: 'inherit',
    windowsHide: true,
    env: {
      ...process.env,
      PYTHONUNBUFFERED: '1',
      DATABASE_URL: 'sqlite+aiosqlite:///gem_radar_standalone.db',
    },
  }
);

proc.on('close', (code) => process.exit(code));
