; OneQMultiA Windows 安装程序（Inno Setup 6）
; 由 scripts/build_windows.ps1 传入 /DRepoRoot= 与 /DMyAppVersion=

#ifndef RepoRoot
  #define RepoRoot ".."
#endif
#ifndef MyAppVersion
  #define MyAppVersion "0.2.0"
#endif

#define MyAppName "OneQMultiA"
#define MyAppPublisher "OneQMultiA"
#define MyAppURL "https://github.com/JING-XINXING/OneQMultiA"
#define MyAppExeName "OneQMultiA.exe"

[Setup]
AppId={{A7C3E91F-4B2D-48A1-9E6C-1F0D8B7A6C25}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir={#RepoRoot}\release
OutputBaseFilename=OneQMultiA-{#MyAppVersion}-win64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
SetupIconFile={#RepoRoot}\packaging\icons\OneQMultiA.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#RepoRoot}\dist\OneQMultiA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RepoRoot}\packaging\windows\start_chrome_cdp.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\{#MyAppName} CDP Chrome"; Filename: "{app}\start_chrome_cdp.bat"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
