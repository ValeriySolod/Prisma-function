; Inno Setup script for Prisma Function.
;
; Builds a Windows installer around the single-file PyInstaller executable
; already produced by the release workflow. Does not touch application
; runtime data (%LOCALAPPDATA%\PrismaFunction\) or the published-output
; Documents directory; it only installs, shortcuts, and uninstalls the
; application binary.
;
; Local build:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\PrismaFunction.iss
; (defaults to packaging dist\PrismaFunction.exe as version 0.0.0)
;
; CI build (see .github/workflows/release.yml):
;   ISCC.exe /DAppVersion=<version> /DSourceExe=<path-to-exe> /DOutputDir=<dir> ^
;     installer\PrismaFunction.iss

#define AppName "Prisma Function"
#define AppExeName "PrismaFunction.exe"
#define AppPublisher "Prisma Function"
#define AppURL "https://github.com/ValeriySolod/Prisma-function"

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceExe
  #define SourceExe "..\dist\PrismaFunction.exe"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif

[Setup]
AppId={{51260825-E4A5-40A4-AF40-0CEA4ED3B5BF}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeName}
OutputDir={#OutputDir}
OutputBaseFilename=PrismaFunction-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; DestName: "{#AppExeName}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
