# FlipFlop Platform - Docker Compose Startup Script
# Usage: .\start-docker.ps1 [command] [-Service servicename] [-NoCache]
# Commands: up, down, restart, logs, status, build, clean

param(
    [ValidateSet("up", "down", "restart", "logs", "status", "build", "clean")]
    [string]$Command = "up",
    [string]$Service = "",
    [switch]$NoCache = $false
)

Write-Host "[*] FlipFlop Platform - Docker Compose Manager" -ForegroundColor Cyan

# Verify Docker is running
try {
    $null = docker ps 2>&1
    Write-Host "[OK] Docker is running" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Docker daemon is not running" -ForegroundColor Red
    exit 1
}

switch ($Command) {
    "up" {
        Write-Host "[*] Starting all services..." -ForegroundColor Cyan
        docker-compose up -d
        docker-compose ps
        Write-Host ""
        Write-Host "URLs: Admin: http://localhost:4312 | Frontend: http://localhost:4313 | API: http://localhost:4311" -ForegroundColor Green
    }
    "down" {
        Write-Host "[*] Stopping all services..." -ForegroundColor Yellow
        docker-compose down
    }
    "restart" {
        if ($Service) {
            docker-compose restart $Service
        } else {
            docker-compose restart
        }
    }
    "logs" {
        if ($Service) {
            docker-compose logs -f $Service
        } else {
            docker-compose logs -f
        }
    }
    "status" {
        docker-compose ps
    }
    "build" {
        docker-compose build 
    }
    "clean" {
        docker-compose down
        docker system prune -f
    }
}
