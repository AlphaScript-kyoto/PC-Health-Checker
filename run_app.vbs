' パソコンちぇっ君 — 開発起動ランチャー
' ダブルクリックで run_app.bat を開きます（作業フォルダをスクリプト位置に固定）
Option Explicit
Dim fso, sh, dir, bat
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
bat = dir & "\run_app.bat"

If Not fso.FileExists(bat) Then
  MsgBox "run_app.bat が見つかりません。" & vbCrLf & bat, vbCritical, "パソコンちぇっ君"
  WScript.Quit 1
End If

sh.CurrentDirectory = dir
' 第2引数 1 = コンソール表示（失敗原因が見える） / 0 だと失敗しても無言になります
sh.Run "cmd /c """ & bat & """", 1, False
