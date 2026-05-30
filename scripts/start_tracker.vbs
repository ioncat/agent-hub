Set shell = CreateObject("WScript.Shell")
Set fso   = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))

' ── Read TRACKER_PORT from .env (app reads everything else itself) ────────────
port = "8080"
envFile = root & "\.env"
If fso.FileExists(envFile) Then
    Set f = fso.OpenTextFile(envFile, 1)
    Do While Not f.AtEndOfStream
        line = Trim(f.ReadLine())
        If Left(line, 1) <> "#" And InStr(line, "=") > 0 Then
            key = Trim(Left(line, InStr(line, "=") - 1))
            val = Trim(Mid(line, InStr(line, "=") + 1))
            If key = "TRACKER_PORT" Then port = val
        End If
    Loop
    f.Close
End If

' ── Find venv python — hard fail if missing ───────────────────────────────────
pythonExe = root & "\.venv\Scripts\python.exe"
If Not fso.FileExists(pythonExe) Then
    pythonExe = root & "\venv\Scripts\python.exe"
End If
If Not fso.FileExists(pythonExe) Then
    MsgBox "Virtual environment not found." & vbCrLf & vbCrLf & _
           "Run in project root:" & vbCrLf & _
           "  python -m venv .venv" & vbCrLf & _
           "  .venv\Scripts\pip install -r requirements.txt", _
           vbCritical, "agent-hub — Tracker"
    WScript.Quit
End If

' ── Build BAT ─────────────────────────────────────────────────────────────────
bat = fso.GetSpecialFolder(2) & "\agent_hub_tracker.bat"
Set f = fso.OpenTextFile(bat, 2, True)
f.WriteLine "@echo off"
f.WriteLine "title agent-hub — Vacancy Tracker :" & port
f.WriteLine "for /f ""tokens=5"" %%a in ('netstat -aon ^| findstr "":"  & port & " "" ^| findstr ""LISTENING"" 2^>nul') do taskkill /f /pid %%a >nul 2>&1"
f.WriteLine "cd /d """ & root & """"
f.WriteLine "echo."
f.WriteLine "echo  Vacancy Tracker — http://localhost:" & port
f.WriteLine "echo  Press Ctrl+C to stop"
f.WriteLine "echo."
f.WriteLine """" & pythonExe & """ -m uvicorn web.api:app --reload --host 127.0.0.1 --port " & port
f.Close

' ── Launch and open browser ───────────────────────────────────────────────────
shell.Run "cmd /k """ & bat & """", 1, False
WScript.Sleep 4000
shell.Run "http://localhost:" & port
