Option Explicit

Dim sh, fso, root, desktop, electron, modules, cmd
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
desktop = fso.BuildPath(root, "desktop")
electron = fso.BuildPath(desktop, "node_modules\electron\dist\electron.exe")
modules = fso.BuildPath(desktop, "node_modules\electron")

If Not fso.FolderExists(modules) Then
  sh.CurrentDirectory = desktop
  sh.Run "cmd /c npm install", 1, True
End If

If Not fso.FileExists(electron) Then
  MsgBox "Electron not found." & vbCrLf & "Run npm install in the desktop folder.", 16, "PC Health"
  WScript.Quit 1
End If

If Not fso.FileExists(fso.BuildPath(root, ".venv\Scripts\pythonw.exe")) And _
   Not fso.FileExists(fso.BuildPath(root, ".venv\Scripts\python.exe")) Then
  MsgBox "Python venv (.venv) not found." & vbCrLf & "Follow README setup, then try again.", 48, "PC Health"
End If

sh.CurrentDirectory = desktop
cmd = Chr(34) & electron & Chr(34) & " " & Chr(34) & desktop & Chr(34)
sh.Run cmd, 0, False
