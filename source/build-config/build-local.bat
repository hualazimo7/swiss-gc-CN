@echo off
REM Swiss build wrapper - runs the MSYS2 toolchain
REM Usage: build-local.bat dev
REM        build-local.bat all
if not exist C:\msys64\usr\bin\bash.exe (
  echo MSYS2 not found at C:\msys64
  pause
  exit /b 1
)
C:\msys64\usr\bin\bash.exe -lc "bash /d/workbuddy/swiss-gc/build-local.sh %*"
echo.
echo exit code: %ERRORLEVEL%
pause
