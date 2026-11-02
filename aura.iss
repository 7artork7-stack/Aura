; Instalador de Aura (Inno Setup 6)
; Colocar este archivo en la carpeta del proyecto (junto a "dist" y "recursos"),
; abrirlo con Inno Setup y pulsar Compile (Ctrl+F9).

[Setup]
AppName=Aura
AppVersion=1.0
AppPublisher=Aaron
; Se instala por usuario: la app guarda las descargas junto al .exe y en
; "Program Files" Windows bloquearía la escritura.
DefaultDirName={localappdata}\Programs\Aura
DefaultGroupName=Aura
PrivilegesRequired=lowest
OutputDir=instalador
OutputBaseFilename=Aura-Setup
SetupIconFile=recursos\logo.ico
UninstallDisplayIcon={app}\Aura.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear icono en el escritorio"; Flags: unchecked

[Files]
; Antes de compilar: dist\Aura debe tener ffmpeg.exe y ffprobe.exe,
; y NO debe tener la carpeta "descargas" de tus pruebas.
Source: "dist\Aura\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Aura"; Filename: "{app}\Aura.exe"
Name: "{autodesktop}\Aura"; Filename: "{app}\Aura.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Aura.exe"; Description: "Abrir Aura"; Flags: nowait postinstall skipifsilent
