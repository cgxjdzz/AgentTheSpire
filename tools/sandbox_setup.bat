@echo off
setlocal
echo ============================================
echo  AgentTheSpire Sandbox Install Test
echo  %DATE% %TIME%
echo ============================================
echo.

:: ── 1. Python 설치 ──────────────────────────────────────────
echo [1/5] Python 3.12 다운로드 및 설치...
curl -L -o C:\python_installer.exe https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe
C:\python_installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
if errorlevel 1 ( echo [FAIL] Python 설치 실패 & goto :error )
:: PATH 반영
set "PATH=C:\Program Files\Python312;C:\Program Files\Python312\Scripts;%PATH%"
python --version
echo [OK] Python 설치 완료

:: ── 2. Node.js 설치 ─────────────────────────────────────────
echo.
echo [2/5] Node.js 20 LTS 다운로드 및 설치...
curl -L -o C:\node_installer.msi https://nodejs.org/dist/v20.17.0/node-v20.17.0-x64.msi
msiexec /i C:\node_installer.msi /quiet /norestart
if errorlevel 1 ( echo [FAIL] Node.js 설치 실패 & goto :error )
set "PATH=C:\Program Files\nodejs;%PATH%"
node --version
npm --version
echo [OK] Node.js 설치 완료

:: ── 3. AgentTheSpire 파일 복사 ──────────────────────────────
echo.
echo [3/5] AgentTheSpire 파일 복사 중...
xcopy /E /I /Q C:\AgentTheSpire_host C:\AgentTheSpire_test
cd /d C:\AgentTheSpire_test
echo [OK] 복사 완료

:: ── 4. tools\install.bat 执行 (不含本地图像生成) ───────────
echo.
echo [4/5] tools\install.bat 执行...
echo n | call tools\install.bat
if errorlevel 1 ( echo [FAIL] tools\install.bat 失败 & goto :error )

:: ── 5. 결과 검증 ────────────────────────────────────────────
echo.
echo [5/5] 설치 결과 검증...
echo --- Python packages ---
pip list | findstr /i "fastapi uvicorn rembg litellm pillow"
echo --- Frontend build output ---
if exist "frontend\dist\index.html" (
    echo [OK] frontend/dist/index.html 존재
) else (
    echo [FAIL] frontend/dist/index.html 없음
)
echo --- Backend entry ---
if exist "backend\main.py" (
    echo [OK] backend/main.py 존재
) else (
    echo [FAIL] backend/main.py 없음
)

echo.
echo ============================================
echo  테스트 완료: 성공
echo  로그: C:\sandbox_output\install_log.txt
echo ============================================
goto :end

:error
echo.
echo ============================================
echo  테스트 실패 - 위 오류 확인
echo ============================================
exit /b 1

:end
:: 결과 요약을 별도 파일로도 저장
echo SANDBOX TEST DONE: %DATE% %TIME% > C:\sandbox_output\result.txt
python --version >> C:\sandbox_output\result.txt 2>&1
node --version >> C:\sandbox_output\result.txt 2>&1
pip show fastapi >> C:\sandbox_output\result.txt 2>&1
if exist "C:\AgentTheSpire_test\frontend\dist\index.html" echo frontend build: OK >> C:\sandbox_output\result.txt




