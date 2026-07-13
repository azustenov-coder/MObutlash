@echo off
chcp 65001 >nul
echo ===================================================
echo MO-BUTLASH loyihasi GitHub'ga yuklanmoqda...
echo ===================================================

git add .
git commit -m "Kunlik avtomatik saqlash: %date% %time%"
git push

echo.
echo ===================================================
echo Barcha o'zgarishlar muvaffaqiyatli saqlandi!
echo ===================================================
pause
