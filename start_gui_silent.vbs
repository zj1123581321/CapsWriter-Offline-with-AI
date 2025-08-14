' CapsWriter GUI 静默启动脚本
' 直接启动GUI，无命令行窗口

Set oShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' 获取脚本所在目录（项目根目录）
projectRoot = fso.GetParentFolderName(WScript.ScriptFullName)

' 检查虚拟环境和GUI脚本是否存在
pythonPath = projectRoot & "\venv\Scripts\python.exe"
trayScript = projectRoot & "\gui\tray_gui_launcher.py"

If Not fso.FileExists(pythonPath) Then
    MsgBox "Error: Python virtual environment not found" & vbCrLf & _
           "Please create and configure virtual environment first", vbCritical, "CapsWriter"
    WScript.Quit 1
End If

If Not fso.FileExists(trayScript) Then
    MsgBox "Error: GUI launcher script not found", vbCritical, "CapsWriter"
    WScript.Quit 1
End If

' 设置工作目录为项目根目录并静默启动GUI
' (窗口样式 0 = 隐藏窗口，不显示命令行)
oShell.CurrentDirectory = projectRoot
command = """" & pythonPath & """ """ & trayScript & """"
oShell.Run command, 0, False