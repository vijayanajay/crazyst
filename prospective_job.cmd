@echo off
rem The nightly prospective job (docs/prospective_protocol.md "Operations"):
rem data refresh (self-gating, retries next run) then virgin-fold scoring.
rem Logs: data/prospective.log (wrapper), data/refresh.log, data/scheduler.log.
cd /d D:\Code\crazyst
set PYTHONIOENCODING=utf-8
.venv\Scripts\python.exe -m src.prospective.job >> data\job_wrapper.log 2>&1
