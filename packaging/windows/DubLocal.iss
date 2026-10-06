#ifndef AppVersion
  #error AppVersion must be supplied by the beta build script.
#endif
#ifndef SourceRoot
  #error SourceRoot must be supplied by the beta build script.
#endif
#ifndef RepoRoot
  #error RepoRoot must be supplied by the beta build script.
#endif

[Setup]
AppId={{E4A1CBFA-61D8-4D7F-979A-654A0A464DD4}
AppName=DubLocal Beta
AppVersion={#AppVersion}
AppPublisher=DubLocal contributors
AppPublisherURL=https://github.com/ArrowSK/dublocal
AppSupportURL=https://github.com/ArrowSK/dublocal/issues
DefaultDirName={localappdata}\DubLocal Launcher
DefaultGroupName=DubLocal
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#RepoRoot}\dist
OutputBaseFilename=DubLocal-{#AppVersion}-Windows-Setup-unsigned
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\DubLocal.cmd

[Files]
Source: "{#SourceRoot}\DubLocal.cmd"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\Stop-DubLocal.cmd"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\bootstrap\*"; DestDir: "{app}\bootstrap"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RepoRoot}\LICENSE"; DestDir: "{app}"; DestName: "License.txt"; Flags: ignoreversion
Source: "{#RepoRoot}\THIRD_PARTY_LICENSES.md"; DestDir: "{app}"; DestName: "Third-Party Licenses.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\DubLocal"; Filename: "{app}\DubLocal.cmd"
Name: "{autoprograms}\Stop DubLocal"; Filename: "{app}\Stop-DubLocal.cmd"

[Run]
Filename: "{app}\DubLocal.cmd"; Description: "Launch DubLocal"; Flags: nowait postinstall skipifsilent
