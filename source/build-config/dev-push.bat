@echo off
REM Example: build the localised Swiss and push it to a running Swiss via wiiload.
REM
REM Configure these three paths for your machine, or set the env vars:
REM   SWISS_GC_REPO   : path to your emukidid/swiss-gc working copy
REM   SWISS_GC_I18N   : path to this localisation repository
REM   MSYS_BASH       : path to MSYS2 usr/bin/bash.exe
REM
REM Usage:  dev-push.bat <gamecube-ip> [inc^|dev^|all]

setlocal
if "%~1"=="" (
  echo usage: dev-push.bat ^<gamecube-ip^> [inc^|dev^|all]
  echo example: dev-push.bat 192.168.1.42
  exit /b 1
)
if "%SWISS_GC_REPO%"=="" set SWISS_GC_REPO=..\swiss-gc
if "%SWISS_GC_I18N%"=="" set SWISS_GC_I18N=..
if "%MSYS_BASH%"=="" set MSYS_BASH=C:\msys64\usr\bin\bash.exe
set GCIP=%~1
set TARGET=%~2
if "%TARGET%"=="" set TARGET=inc

echo === preflight ===
py -3 "%SWISS_GC_I18N%\source\tools\preflight.py"
if errorlevel 1 (echo PREFLIGHT FAILED - nothing built. & exit /b 1)

echo === build (%TARGET%) ===
"%MSYS_BASH%" -lc "bash '%SWISS_GC_REPO%/build-local.sh' %TARGET%"
if errorlevel 1 (echo BUILD FAILED - nothing pushed. & exit /b 1)

echo === push to %GCIP% ===
py -3 "%SWISS_GC_I18N%\tools\wiiload.py" %GCIP% "%SWISS_GC_REPO%\cube\swiss\swiss.dol"
if errorlevel 1 (echo PUSH FAILED - check the IP and that Swiss is running. & exit /b 1)
endlocal
