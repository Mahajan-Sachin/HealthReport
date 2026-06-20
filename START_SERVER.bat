@echo off
echo Starting MediScan AI...
call conda activate langgraph_env
cd /d C:\Users\sachi\Desktop\UltimateAiProject
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
pause
