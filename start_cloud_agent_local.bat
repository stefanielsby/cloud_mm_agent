@echo off
title 🚢 MM Agent (Cloud Edition - Local Test) 🚢
chcp 65001 > null
echo 🚢 Starter Cloud MM Agent lokalt til test...
cd /d "%~dp0"
call venv\Scripts\activate.bat
streamlit run cloud_mm_agent.py
pause
