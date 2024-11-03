# Example.nsi - An NSIS script example
Outfile "ReadCV.exe"
InstallDir "$PROGRAMFILES\ReadCV"
Page Directory
Page InstFiles

Section
    SetOutPath "$INSTDIR"
    File "ReadCV.exe"
SectionEnd
