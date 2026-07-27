Option Explicit
Dim fso, sh, dir, bat
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
bat = dir & "\run_app.bat"

If Not fso.FileExists(bat) Then
  MsgBox "run_app.bat not found:" & vbCrLf & bat, vbCritical, "PC Chekkun"
  WScript.Quit 1
End If

sh.CurrentDirectory = dir
sh.Run "cmd /c """ & bat & """", 1, False
