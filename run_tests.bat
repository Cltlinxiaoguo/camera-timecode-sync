@echo off
REM Windows 一键执行单元测试（默认排除 slow 标记）
chcp 65001 >NUL
setlocal
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

pushd %~dp0

echo [run_tests] pytest -q -m "not slow"
python -m pytest -q -m "not slow"
set CODE=%ERRORLEVEL%

popd
exit /b %CODE%
