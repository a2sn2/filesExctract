#ifndef SourceDir
  #define SourceDir "."
#endif

#define MyAppName "FilesExtract"
#define MyAppVersion "0.4.0"
#define MyAppPublisher "ALHassan ALShami"
#define MyAppExeName "FilesExtract.exe"

[Setup]
AppId={{A16AF1D7-3E55-49C8-92A9-6F3947731D1C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\FilesExtract
DefaultGroupName=FilesExtract
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=FilesExtract-Full-Setup-v0.4.0
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
DisableProgramGroupPage=yes

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\FilesExtract"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\FilesExtract"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch FilesExtract"; Flags: nowait postinstall skipifsilent
