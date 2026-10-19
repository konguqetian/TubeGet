@echo off
REM Windows x64 打包：PyInstaller -> Inno Setup 安装程序
REM 用法：build\build_win.bat

setlocal
cd /d "%~dp0.."

set PY=%PYTHON%
if "%PY%"=="" set PY=python

echo ==^> 图标
"%PY%" build\make_icon.py resources

echo ==^> PyInstaller 打包
"%PY%" -m PyInstaller build\TubeGet.spec --noconfirm --clean
if errorlevel 1 goto :fail

echo ==^> 生成安装程序
where iscc >nul 2>nul
if errorlevel 1 (
  echo 未找到 iscc，尝试安装 Inno Setup...
  choco install innosetup -y --no-progress
)
iscc build\installer.iss
if errorlevel 1 goto :fail

echo ==^> 完成
dir dist\*.exe
exit /b 0

:fail
echo 打包失败
exit /b 1
