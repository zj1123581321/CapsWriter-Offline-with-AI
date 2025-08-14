' CapsWriter GUI Tray Launcher (Silent Start)
' This script starts the GUI tray application without showing command line window

Set oShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get script directory
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Check if virtual environment exists
pythonPath = scriptDir & "\venv\Scripts\python.exe"
trayScript = scriptDir & "\tray_gui_launcher.py"

If Not fso.FileExists(pythonPath) Then
    MsgBox "Error: Virtual environment not found" & vbCrLf & _
           "Please create and configure virtual environment first", vbCritical, "CapsWriter"
    WScript.Quit 1
End If

If Not fso.FileExists(trayScript) Then
    MsgBox "Error: GUI tray launcher script not found", vbCritical, "CapsWriter"
    WScript.Quit 1
End If

' Start GUI tray application (window style 0 = hidden window, no command line)
command = """" & pythonPath & """ """ & trayScript & """"
oShell.Run command, 0, False