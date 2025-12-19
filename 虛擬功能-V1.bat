@echo off

:: 設定時間
set "fullDate=%DATE%"
set "shortDate=%fullDate:~0,10%"
set "shortDate=%shortDate:/=-%"
set "timePart=%TIME:~0,8%"
set "timePart=%timePart::=%" 
set "shortDate=%shortDate%-%timePart%"

goto main_menu

:main_menu
cls
echo.
echo 歡迎到功能選單:
echo ===================
echo 1. 虛擬環境設置
echo 2. 啟動虛擬環境
echo 3. 備份功能
echo 4. 離開
echo.
set /p choice=請輸入選擇（1-4）:
echo.

if "%choice%"=="1" goto setup_env
if "%choice%"=="2" goto activate_env
if "%choice%"=="3" goto backup_menu
if "%choice%"=="4" exit

:setup_env
:: ───────────────────────────────────────────────
::  setup_env.bat — 自動在本資料夾建立 venv 並安裝依賴
::  適用：Windows 10 / 11
:: ───────────────────────────────────────────────
setlocal

:: 1. 提示開始
echo.
echo ================================================
echo    Python 虛擬環境 一鍵建立與依賴安裝
echo ================================================
echo.

:: 2. 確認 Python 可用
python -V >nul 2>&1
if errorlevel 1 (
    echo [錯誤] 找不到 python 指令，請先確認已安裝並加入 PATH。
    pause
    exit /b 1
)

:: 3. 如果已存在 venv，詢問是否重建
if exist "venv\Scripts\activate.bat" (
    echo 已偵測到現有虛擬環境 venv。
    set /p REBUILD="是否要刪除並重建？(Y/N) [N]："
    if /I "%REBUILD%"=="Y" (
        echo 刪除舊的 venv...
        rmdir /s /q venv
    ) else (
        echo 使用現有虛擬環境，不做變更。
        goto :ACTIVATE
    )
)

:: 4. 建立虛擬環境
echo 建立虛擬環境 venv...
python -m venv venv
if errorlevel 1 (
    echo [錯誤] 建立虛擬環境失敗！
    pause
    exit /b 1
)

:ACTIVATE
:: 5. 啟動 venv 並安裝依賴
echo.
echo 啟動虛擬環境...
call venv\Scripts\activate.bat

echo.
if exist "requirements.txt" (
    echo 找到 requirements.txt，開始安裝依賴...
    pip install --upgrade pip
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [警告] 依賴安裝過程出現錯誤，請檢查 requirements.txt。
    ) else (
        echo 依賴安裝完成。
    )
) else (
    echo 未找到 requirements.txt，跳過依賴安裝。
)

:: 6. 最後提示與選單
echo.
echo ================================================
echo    虛擬環境已準備完畢！
echo ================================================
echo.

:ENV_MENU
echo.
echo 現在你可以選擇以下操作：
echo   1. 啟動虛擬環境並打開命令提示符
echo   2. 返回主選單
echo.
set /p ENV_CHOICE="請輸入選項 (1 或 2): "

if "%ENV_CHOICE%"=="1" (
    echo 啟動虛擬環境並打開命令提示符...
    start cmd /k "call venv\Scripts\activate.bat"
    exit
) else if "%ENV_CHOICE%"=="2" (
    goto main_menu
) else (
    echo 無效的選項。
    goto ENV_MENU
)

endlocal

goto main_menu

:activate_env
if not exist "venv\Scripts\activate.bat" (
    echo 虛擬環境尚未建立，請先設置虛擬環境。
    pause
    goto main_menu
)
echo 啟動虛擬環境...
call venv\Scripts\activate.bat
start cmd /k "call venv\Scripts\activate.bat"
exit

:backup_menu
cls
echo.
echo 備份你的資料夾啦:
echo ===================
echo 1. 備份當前檔案
echo 2. 還原檔案
echo 3. 刪除超過3個月以上的備份檔案
echo 4. 返回主選單
IF NOT EXIST "C:\Program Files\7-Zip\7z.exe" (
    echo 目前尚未安裝7-Zip, 請先安裝此程式
    echo https://www.developershome.com/7-zip/download.asp
)
echo.
set /p choice=請輸入選擇（1-4）:
echo.

if "%choice%"=="1" goto zip
if "%choice%"=="2" goto unzip
if "%choice%"=="3" goto delete_old
if "%choice%"=="4" goto main_menu

:zip
set /p name=請輸入備份的名稱（e.g. 測試版 / v1.2 等）:
set backupFolder=備份

if not exist "%backupFolder%" mkdir "%backupFolder%"

echo 壓縮中...
"C:\Program Files\7-Zip\7z.exe" a -tzip   ".\備份\%shortDate%_%name%.zip"  ".\" -xr!備份

echo 完成壓縮！

goto backup_menu

:unzip
set backupFolder=備份
setlocal enabledelayedexpansion

echo 備份檔案:
set counter=0
for /f "tokens=*" %%A in ('dir /b %backupFolder%\*.zip') do (
  set /a counter+=1
  echo !counter!. %%A
  set "file!counter!=%%~nA"
)

set /p file=請選擇備份檔案的編號來解壓縮:
set "selectedFile=!file%file%!"
echo 你選擇的檔案是 %selectedFile%

:: 刪除目前資料夾中，除了 bat 與 備份 資料夾以外的所有檔案與資料夾
echo.
echo ?? 開始清除目前資料夾（排除 .bat 檔與 備份資料夾）...
for %%F in (*.*) do (
    if /I not "%%~nxF"=="%~nx0" (
        if /I not "%%~nxF"=="%backupFolder%" (
            del /f /q "%%F" 2>nul
        )
    )
)
for /d %%D in (*) do (
    if /I not "%%~nxD"=="%backupFolder%" (
        rmdir /s /q "%%D" 2>nul
    )
)
echo 清除完成！

:: 解壓縮還原
echo.
echo ?? 正在還原備份...
"C:\Program Files\7-Zip\7z.exe" x "%backupFolder%\%selectedFile%.zip" -o"." -aoa
echo ? 完成解壓縮！

endlocal
goto backup_menu

:delete_old
echo 刪除超過3個月以上的備份檔案...
forfiles /p "備份" /s /m *.zip /d -90 /c "cmd /c del @path"
echo 完成刪除！

goto backup_menu