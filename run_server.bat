@echo off
cd /d "D:\quran_helper"
echo Starting Django server...
echo.
echo Server will be available at: http://127.0.0.1:8000
echo Press Ctrl+C to stop the server
echo.
venv\Scripts\python manage.py runserver 127.0.0.1:8000
pause
