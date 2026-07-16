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
  MsgBox "Electron が見つかりません。" & vbCrLf & "desktop フォルダで npm install を実行してください。", 16, "PC Health"
  WScript.Quit 1
End If

' Prefer venv for backend; warn if missing (Electron still starts and shows error UI)
If Not fso.FileExists(fso.BuildPath(root, ".venv\Scripts\pythonw.exe")) And _
   Not fso.FileExists(fso.BuildPath(root, ".venv\Scripts\python.exe")) Then
  MsgBox "Python 仮想環境 (.venv) が見つかりません。" & vbCrLf & _
         "初回は README のセットアップ後に再実行してください。", 48, "PC Health"
End If

sh.CurrentDirectory = desktop
cmd = Chr(34) & electron & Chr(34) & " " & Chr(34) & desktop & Chr(34)
' 0 = hidden console; False = don't wait (second click focuses existing window)
sh.Run cmd, 0, False
