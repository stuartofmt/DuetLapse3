@echo off
rem Start the program with its venv (made by Prepare in Prep_and_Package). With no venv - e.g. just
rem unzipped from a release - it is made first and Code\dsf\requirements.txt (with Code\dsf\requirements-windows.txt, if there is
rem one) is installed into it.
rem The program runs with no window (closing this one does not stop it): stop it with its Terminate
rem button.  run.bat console runs it in this window, showing its messages.
cd /d "%~dp0"
set CONSOLE=
set ARGS=%*
if /i not "%~1"=="console" goto args
set CONSOLE=1
set ARGS=
:nextarg
shift
if "%~1"=="" goto args
set ARGS=%ARGS% %1
goto nextarg
:args
set REQS=-r "Code\dsf\requirements.txt"
if exist "Code\dsf\requirements-windows.txt" set REQS=%REQS% -r "Code\dsf\requirements-windows.txt"
if not exist venv\Scripts\python.exe (
  echo First run: making the venv and installing Code\dsf\requirements.txt into it
  py -3 -m venv venv 2>nul || python -m venv venv || goto novenv
  venv\Scripts\python.exe -m pip install %REQS% || goto nopip
)
if defined CONSOLE goto console
set RUN_ARGS=-u "Code\dsf\duetLapse3.py" %ARGS%
set RUN_PY=%~dp0venv\Scripts\python.exe
echo Starting Code\dsf\duetLapse3.py with no window - checking that it keeps running
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Start-Process -FilePath $env:RUN_PY -ArgumentList $env:RUN_ARGS -WindowStyle Hidden -PassThru; $null = $p.Handle; if ($p.WaitForExit(5000)) { exit $p.ExitCode }; exit 0"
set CODE=%errorlevel%
if not %CODE%==0 (
  echo.
  echo Code\dsf\duetLapse3.py stopped at once with an error ^(exit code %CODE%^) - run.bat console shows why
  pause
)
exit /b %CODE%
:console
venv\Scripts\python.exe -u Code\dsf\duetLapse3.py %ARGS%
set CODE=%errorlevel%
if not %CODE%==0 (
  echo.
  echo Code\dsf\duetLapse3.py stopped with an error ^(exit code %CODE%^) - see the messages above
  pause
)
exit /b %CODE%
:novenv
echo Could not make the venv: install Python 3 from python.org ^(tick "Add python.exe to PATH"^) and run this again
goto failed
:nopip
echo Could not install the requirements into the venv - see the pip messages above
:failed
rmdir /s /q venv 2>nul
pause
exit /b 1
