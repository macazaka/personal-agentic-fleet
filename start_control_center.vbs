' 1-Click Silent Background Launcher for Personal Agentic Fleet Control Center
Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
AppScript = ScriptDir & "\fleet\app.py"

Args = ""
If WScript.Arguments.Count > 0 Then
    For i = 0 To WScript.Arguments.Count - 1
        Args = Args & " " & WScript.Arguments(i)
    Next
End If

If FSO.FileExists("C:\Python314\pythonw.exe") Then
    WshShell.Run """C:\Python314\pythonw.exe"" """ & AppScript & """" & Args, 0, False
Else
    WshShell.Run "pythonw """ & AppScript & """" & Args, 0, False
End If

Set WshShell = Nothing
Set FSO = Nothing
