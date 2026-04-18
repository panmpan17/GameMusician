@echo off
cd /d "%~dp0"

if exist ".\source\Scripts\activate.bat" (
	call ".\source\Scripts\activate.bat"
) else if exist ".\env\Scripts\activate.bat" (
	call ".\env\Scripts\activate.bat"
) else (
	echo Could not find a virtual environment activation script.
	echo Checked: .\source\Scripts\activate.bat and .\env\Scripts\activate.bat
	pause
	exit /b 1
)

python main.py gui
