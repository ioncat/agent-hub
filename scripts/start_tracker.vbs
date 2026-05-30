Set shell = CreateObject("WScript.Shell")
Set fso   = CreateObject("Scripting.FileSystemObject")

root    = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
kmpDir  = fso.GetParentFolderName(root) & "\knowledge-mirror-parser"

' ── Read .env ────────────────────────────────────────────────────────────────
kmpPort     = "8001"
trackerPort = "8080"
dbPath      = root & "\db\agent.db"
candidateName = "Oleksii_Bondarenko"

envFile = root & "\.env"
If fso.FileExists(envFile) Then
    Set f = fso.OpenTextFile(envFile, 1)
    Do While Not f.AtEndOfStream
        line = Trim(f.ReadLine())
        If Left(line, 1) <> "#" And InStr(line, "=") > 0 Then
            key = Trim(Left(line, InStr(line, "=") - 1))
            val = Trim(Mid(line, InStr(line, "=") + 1))
            If key = "DB_PATH"        Then dbPath        = val
            If key = "CANDIDATE_NAME" Then candidateName = val
            If key = "KMP_PORT"       Then kmpPort       = val
            If key = "TRACKER_PORT"   Then trackerPort   = val
        End If
    Loop
    f.Close
End If

' ── kmp-service BAT ──────────────────────────────────────────────────────────
kmpBat = fso.GetSpecialFolder(2) & "\agent_hub_kmp.bat"
Set f = fso.OpenTextFile(kmpBat, 2, True)
f.WriteLine "@echo off"
f.WriteLine "title agent-hub — kmp-service :" & kmpPort
f.WriteLine ":: Free port if occupied"
f.WriteLine "for /f ""tokens=5"" %%a in ('netstat -aon ^| findstr "":"  & kmpPort & " "" ^| findstr ""LISTENING"" 2^>nul') do taskkill /f /pid %%a >nul 2>&1"
f.WriteLine "cd /d """ & kmpDir & """"
f.WriteLine "echo."
f.WriteLine "echo  [kmp-service] http://localhost:" & kmpPort
f.WriteLine "echo  Press Ctrl+C to stop"
f.WriteLine "echo."
f.WriteLine "python -m uvicorn api:app --reload --host 127.0.0.1 --port " & kmpPort
f.Close

' ── web tracker BAT ──────────────────────────────────────────────────────────
trackerBat = fso.GetSpecialFolder(2) & "\agent_hub_tracker.bat"
Set f = fso.OpenTextFile(trackerBat, 2, True)
f.WriteLine "@echo off"
f.WriteLine "title agent-hub — Vacancy Tracker :" & trackerPort
f.WriteLine ":: Free port if occupied"
f.WriteLine "for /f ""tokens=5"" %%a in ('netstat -aon ^| findstr "":"  & trackerPort & " "" ^| findstr ""LISTENING"" 2^>nul') do taskkill /f /pid %%a >nul 2>&1"
f.WriteLine "cd /d """ & root & """"
f.WriteLine "set DB_PATH=" & dbPath
f.WriteLine "set CANDIDATE_NAME=" & candidateName
f.WriteLine "set KMP_BASE_URL=http://localhost:" & kmpPort
f.WriteLine "echo."
f.WriteLine "echo  [Tracker] http://localhost:" & trackerPort
f.WriteLine "echo  DB: " & dbPath
f.WriteLine "echo  Press Ctrl+C to stop"
f.WriteLine "echo."
f.WriteLine "python -m uvicorn web.api:app --reload --host 127.0.0.1 --port " & trackerPort
f.Close

' ── Launch ───────────────────────────────────────────────────────────────────
wtExe = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Microsoft\WindowsApps\wt.exe"

If fso.FileExists(wtExe) Then
    ' Windows Terminal: two panes side by side
    shell.Run "wt cmd /k """ & kmpBat & """ ; split-pane -H cmd /k """ & trackerBat & """", 1, False
Else
    ' Fallback: two separate cmd windows
    shell.Run "cmd /k """ & kmpBat & """", 1, False
    WScript.Sleep 500
    shell.Run "cmd /k """ & trackerBat & """", 1, False
End If

' ── Open browser after services start ────────────────────────────────────────
WScript.Sleep 5000
shell.Run "http://localhost:" & trackerPort
