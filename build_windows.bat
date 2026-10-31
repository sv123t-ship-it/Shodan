@echo off
setlocal
cd /d "%~dp0"
py -3 -m venv .venv-build
if errorlevel 1 goto :failed
".venv-build\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 goto :failed
".venv-build\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 goto :failed
".venv-build\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name ShodanExcel shodan_gui.py
if errorlevel 1 goto :failed
echo Build complete: dist\ShodanExcel.exe
exit /b 0
:failed
echo Build failed. Check the error above.
exit /b 1
