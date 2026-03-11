@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ============================================================
echo   Установка ffmpeg для Meet Transcript
echo ============================================================
echo.

:: --- Проверка прав администратора ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Требуются права администратора.
    echo     Закройте это окно, нажмите правой кнопкой на файл
    echo     install_ffmpeg.bat и выберите "Запуск от имени администратора".
    echo.
    pause
    exit /b 1
)

:: --- Проверка: уже установлен? ---
if exist "C:\ffmpeg\bin\ffmpeg.exe" (
    echo [OK] ffmpeg уже установлен в C:\ffmpeg\bin
    goto :add_path
)

where ffmpeg >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] ffmpeg уже доступен в системе.
    goto :done
)

:: --- Скачивание ---
set "FFMPEG_URL=https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
set "FFMPEG_ZIP=%TEMP%\ffmpeg_setup.zip"
set "FFMPEG_EXTRACT=%TEMP%\ffmpeg_extract"
set "FFMPEG_DEST=C:\ffmpeg"

echo [1/4] Скачивание ffmpeg (~80 МБ)...
echo       Источник: www.gyan.dev (официальные сборки)
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Invoke-WebRequest -Uri '%FFMPEG_URL%' -OutFile '%FFMPEG_ZIP%' -UseBasicParsing"

if %errorlevel% neq 0 (
    echo.
    echo [!] Ошибка скачивания. Проверьте подключение к интернету и попробуйте снова.
    pause
    exit /b 1
)

:: --- Распаковка ---
echo [2/4] Распаковка...

if exist "%FFMPEG_EXTRACT%" rmdir /s /q "%FFMPEG_EXTRACT%"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Expand-Archive -Path '%FFMPEG_ZIP%' -DestinationPath '%FFMPEG_EXTRACT%' -Force"

if %errorlevel% neq 0 (
    echo [!] Ошибка распаковки.
    pause
    exit /b 1
)

:: --- Копирование в C:\ffmpeg ---
echo [3/4] Установка в C:\ffmpeg\bin...

if exist "%FFMPEG_DEST%" rmdir /s /q "%FFMPEG_DEST%"
mkdir "%FFMPEG_DEST%\bin"

:: Ищем папку внутри архива (имя зависит от версии)
for /d %%D in ("%FFMPEG_EXTRACT%\ffmpeg-*") do (
    set "SRC_BIN=%%D\bin"
)

if not defined SRC_BIN (
    echo [!] Не удалось найти папку bin внутри архива.
    pause
    exit /b 1
)

copy /y "!SRC_BIN!\ffmpeg.exe"  "%FFMPEG_DEST%\bin\" >nul
copy /y "!SRC_BIN!\ffprobe.exe" "%FFMPEG_DEST%\bin\" >nul

if not exist "%FFMPEG_DEST%\bin\ffmpeg.exe" (
    echo [!] Не удалось скопировать файлы.
    pause
    exit /b 1
)

:: --- Очистка временных файлов ---
del /q "%FFMPEG_ZIP%" >nul 2>&1
rmdir /s /q "%FFMPEG_EXTRACT%" >nul 2>&1

:add_path
:: --- Добавление в системный PATH через реестр (безопасно, без обрезания) ---
echo [4/4] Добавление C:\ffmpeg\bin в системный PATH...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$p = [Environment]::GetEnvironmentVariable('Path','Machine'); " ^
    "if ($p -notlike '*C:\ffmpeg\bin*') { " ^
    "    [Environment]::SetEnvironmentVariable('Path', $p + ';C:\ffmpeg\bin', 'Machine'); " ^
    "    Write-Host '[OK] PATH обновлён'; " ^
    "} else { Write-Host '[OK] C:\ffmpeg\bin уже в PATH'; }"

:done
echo.
echo ============================================================
echo   ffmpeg успешно установлен!
echo   Путь: C:\ffmpeg\bin\ffmpeg.exe
echo.
echo   Теперь запустите Meet Transcript.
echo ============================================================
echo.
pause
