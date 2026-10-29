; Standard NSIS installer with install-time WriteUninstaller.
; This supported custom script avoids running a Windows helper during Linux builds.
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "nsProcess.nsh"
Name "기준실"
InstallDir "$LOCALAPPDATA\Programs\Gijunsil"
InstallDirRegKey HKCU "Software\Gijunsil" "InstallDir"
RequestExecutionLevel user
SetCompressor zlib
SetCompressionLevel 6
ShowInstDetails show
ShowUninstDetails show
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "기준실 설치를 시작합니다"
!define MUI_WELCOMEPAGE_TEXT "견적조건과 부자재 산출을 위한 우리 회사의 업무 프로그램입니다.$\r$\n$\r$\n설치 후 바탕화면의 기준실 아이콘을 실행하고 로그인하세요.$\r$\n$\r$\n이미 실행 중인 기준실이 있다면 먼저 종료해주세요."
!define MUI_FINISHPAGE_RUN "$INSTDIR\Gijunsil.exe"
!define MUI_FINISHPAGE_RUN_TEXT "기준실 실행"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Korean"
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "Windows 64비트가 필요합니다."
    Abort
  ${EndIf}
  ${nsProcess::FindProcess} "Gijunsil.exe" $R0
  ${If} $R0 == 0
    MessageBox MB_ICONEXCLAMATION "기준실을 종료한 뒤 설치를 다시 실행해주세요."
    Abort
  ${EndIf}
FunctionEnd

Section "기준실 설치"
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  !ifdef NSIS_WIN32_MAKENSIS
    File /r "${PROJECT_DIR}\dist\win-unpacked\*"
  !else
    File /r "${PROJECT_DIR}/dist/win-unpacked/*"
  !endif
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\기준실"
  CreateShortcut "$SMPROGRAMS\기준실\기준실.lnk" "$INSTDIR\Gijunsil.exe"
  CreateShortcut "$DESKTOP\기준실.lnk" "$INSTDIR\Gijunsil.exe"
  WriteRegStr HKCU "Software\Gijunsil" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Gijunsil" "DisplayName" "기준실"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Gijunsil" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Gijunsil" "Publisher" "Gijunsil"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Gijunsil" "DisplayIcon" "$INSTDIR\Gijunsil.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Gijunsil" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Gijunsil" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Gijunsil" "NoRepair" 1
SectionEnd

Function un.onInit
  ${nsProcess::FindProcess} "Gijunsil.exe" $R0
  ${If} $R0 == 0
    MessageBox MB_ICONEXCLAMATION "기준실을 종료한 뒤 삭제를 다시 실행해주세요."
    Abort
  ${EndIf}
FunctionEnd
Section "Uninstall"
  SetShellVarContext current
  Delete "$DESKTOP\기준실.lnk"
  Delete "$SMPROGRAMS\기준실\기준실.lnk"
  RMDir "$SMPROGRAMS\기준실"
  !ifdef NSIS_WIN32_MAKENSIS
    !include "${PROJECT_DIR}\.desktop-build\uninstall-files.nsh"
  !else
    !include "${PROJECT_DIR}/.desktop-build/uninstall-files.nsh"
  !endif
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "Software\Gijunsil"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Gijunsil"
  ; Company data resides on the server; local user profile and unknown files are retained.
SectionEnd
