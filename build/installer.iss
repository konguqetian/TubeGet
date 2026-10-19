; Inno Setup 安装脚本（Windows x64）
; 编译：iscc build\installer.iss   （在仓库根目录执行）
;
; 注意：Inno Setup 的相對路徑是相對於「腳本所在目錄」（即 build\）解析的，
; 因此指向仓库根的资源都要寫 ..\ 前綴。

#define MyAppName "TubeGet"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "TubeGet"
#define MyAppURL "https://github.com/konguqetian/TubeGet"
#define MyAppExeName "TubeGet.exe"
#define SrcDir "..\dist\TubeGet"

[Setup]
AppId={{E9A6F2C1-3B44-4A7E-9E21-5C8B7D0A1F22}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=
OutputDir=..\dist
OutputBaseFilename=TubeGet-Windows-x64-Setup
SetupIconFile=..\resources\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
WizardResizable=no
; x64compatible = x64 原生 + Windows on ARM 的 x64 模拟层，ARM 机器也能装
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayName={#MyAppName} {#MyAppVersion}
ChangesAssociations=no
DisableDirPage=auto

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SrcDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[InstallDelete]
Type: filesandordirs; Name: "{app}\bin"
