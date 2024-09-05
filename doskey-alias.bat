@echo off
REM Batch file to create a doskey macro for running a Python script
REM Alias name: autorename
REM Usage: autorename TARGET_DIR
REM This command will run the Python script located at "G:\My Drive\System\Autorename" and pass the TARGET_DIR as an argument.

doskey autorename=python "G:\My Drive\System\Autorename\autorename.py" $*

REM Instructions to make this doskey macro permanent:
REM 1. Save this script as set_aliases.bat in a permanent location on your computer.
REM 2. Press Win + R, type regedit, and press Enter to open the Registry Editor.
REM 3. Navigate to the following key:
REM    HKEY_CURRENT_USER\Software\Microsoft\Command Processor
REM 4. Right-click on the right pane and choose New > String Value.
REM 5. Name this new string value 'AutoRun'.
REM 6. Double-click on 'AutoRun' and set its value to the full path of your set_aliases.bat file,
REM    for example, C:\Path\To\Your\set_aliases.bat.
REM 7. Close the Registry Editor and restart your Command Prompt to apply the changes.