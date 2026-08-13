#ifndef SourceDir
  #define SourceDir "."
#endif
#ifndef OutputDir
  #define OutputDir "dist"
#endif

#define MyAppName "FilesExtract"
#define MyAppVersion "0.5.0"
#define MyAppPublisher "ALHassan ALShami"
#define MyAppExeName "FilesExtract.exe"
#define MyConvertExeName "FilesConvert.exe"

[Setup]
AppId={{A16AF1D7-3E55-49C8-92A9-6F3947731D1C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\FilesExtract
DefaultGroupName=FilesExtract
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=FilesExtract-Full-Setup-v0.5.0
Compression=lzma2/ultra64
SolidCompression=yes
SetupArchitecture=x64
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
DisableProgramGroupPage=yes
CloseApplications=yes
RestartApplications=no

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\FilesExtract"; Filename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\FilesExtract Converter"; Filename: "{app}\{#MyConvertExeName}"
Name: "{autodesktop}\FilesExtract"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{autodesktop}\FilesExtract Converter"; Filename: "{app}\{#MyConvertExeName}"; Tasks: converterdesktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a FilesExtract desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "converterdesktopicon"; Description: "Create a FilesExtract Converter desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch FilesExtract"; Flags: nowait postinstall skipifsilent
