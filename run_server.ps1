# PowerShell script to run Django server
Set-Location "D:\quran_helper"
Write-Host "Starting Django server..." -ForegroundColor Green
Write-Host ""
Write-Host "Server will be available at: http://127.0.0.1:8000" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""
.\venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
