@echo off
rem Start MySQL server (double-click this to turn on the database)
start "MySQL Server" /min "C:\Users\qi\mysql\bin\mysqld.exe" --basedir="C:/Users/qi/mysql" --datadir="C:/Users/qi/mysql/data"
timeout /t 3 >nul
echo.
echo MySQL server is starting...
echo Open DBeaver and connect to see your data.
echo If it was already running, that's fine too.
pause
