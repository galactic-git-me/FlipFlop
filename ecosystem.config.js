module.exports = {
  apps: [
    {
      name: 'db-cleanup',
      script: './flipflop-api/cleanup_db_connections.py',
      interpreter: 'C:\\Users\\mclar\\CODING\\FlipFlop\\flipflop-api\\.venv\\Scripts\\python.exe',
      cwd: 'C:\\Users\\mclar\\CODING\\FlipFlop',
      watch: false,
      autorestart: false,
      // Run every 10 minutes (600 seconds)
      cron: '*/10 * * * *',
      max_memory_restart: '100M',
      env: {
        NODE_ENV: 'production'
      }
    },
    {
      name: 'backend',
      script: './flipflop-api/run_dev.py',
      interpreter: 'C:\\Users\\mclar\\CODING\\FlipFlop\\flipflop-api\\.venv\\Scripts\\python.exe',
      args: '--host 0.0.0.0 --port 4311',
      cwd: 'C:\\Users\\mclar\\CODING\\FlipFlop',
      watch: false,
      env: {
        NODE_ENV: 'development'
      }
    },
    {
      name: 'gemradar-api-18000',
      script: 'C:\\Users\\mclar\\CODING\\FlipFlop\\flipflop-api\\.venv\\Scripts\\python.exe',
      args: '-m uvicorn app.gem_radar_standalone:app --host 127.0.0.1 --port 18000',
      cwd: 'C:\\Users\\mclar\\CODING\\FlipFlop\\flipflop-api',
      watch: false
    },
    {
      name: 'flipflop-admin-3002',
      script: 'npm',
      args: 'run dev -- -p 3002 -H 0.0.0.0',
      cwd: 'C:\\Users\\mclar\\CODING\\FlipFlop\\flipflop-admin',
      watch: false,
      env: {
        NEXT_PUBLIC_API_URL: 'http://localhost:4311'
      }
    }
  ]
};
