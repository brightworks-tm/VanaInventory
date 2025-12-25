Set objShell = CreateObject("Shell.Application")
Set objFSO = CreateObject("Scripting.FileSystemObject")
strPath = objFSO.GetParentFolderName(WScript.ScriptFullName)
' pythonw.exe を使い、ui_inventory.py を実行する（コンソールウィンドウを表示しない）
objShell.ShellExecute "pythonw.exe", "ui_inventory.py", strPath, "runas", 1
