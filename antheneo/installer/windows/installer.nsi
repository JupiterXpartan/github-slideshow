; Antheneo Browser — Windows NSIS Installer Script
; Build: makensis installer.nsi  (from the dist/ directory after PyInstaller)
; Output: Antheneo-Setup-1.0.0.exe

!define APP_NAME        "Antheneo Browser"
!define APP_VERSION     "1.0.0"
!define APP_PUBLISHER   "Antheneo"
!define APP_URL         "https://antheneo.io"
!define APP_EXE         "antheneo.exe"
!define APP_ID          "com.antheneo.browser"
!define INSTALL_DIR     "$PROGRAMFILES64\Antheneo"
!define UNINSTALL_KEY   "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}"

;── Plugins & Config ──────────────────────────────────────────────────────
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"

Name        "${APP_NAME} ${APP_VERSION}"
OutFile     "..\..\dist\Antheneo-Setup-${APP_VERSION}.exe"
InstallDir  "${INSTALL_DIR}"
InstallDirRegKey HKLM "${UNINSTALL_KEY}" "InstallLocation"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
Unicode True

;── MUI Pages ────────────────────────────────────────────────────────────
!define MUI_ICON              "..\..\assets\icon.ico"
!define MUI_UNICON            "..\..\assets\icon.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP_NOSTRETCH
!define MUI_HEADERIMAGE
!define MUI_BGCOLOR           "0D1117"
!define MUI_ABORTWARNING

!define MUI_WELCOMEPAGE_TITLE    "Welcome to Antheneo Browser"
!define MUI_WELCOMEPAGE_TEXT     "Antheneo is a privacy-first browser with a dark cyberpunk UI.$\r$\n$\r$\nBuilt-in ad/tracker blocking, HTTPS upgrading, fingerprint protection, and optional Hacker Mode for authorized security testing.$\r$\n$\r$\nClick Next to continue."

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE   "..\..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN         "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT    "Launch Antheneo Browser"
!define MUI_FINISHPAGE_LINK        "Visit antheneo.io"
!define MUI_FINISHPAGE_LINK_LOCATION "${APP_URL}"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

;── Version Info (shown in file properties) ──────────────────────────────
VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey "ProductName"     "${APP_NAME}"
VIAddVersionKey "ProductVersion"  "${APP_VERSION}"
VIAddVersionKey "CompanyName"     "${APP_PUBLISHER}"
VIAddVersionKey "LegalCopyright"  "© 2025 Antheneo"
VIAddVersionKey "FileDescription" "${APP_NAME} Installer"
VIAddVersionKey "FileVersion"     "${APP_VERSION}.0"

;── Installer Sections ────────────────────────────────────────────────────
Section "Antheneo Browser" SecMain
    SectionIn RO   ; required

    SetOutPath "$INSTDIR"

    ; Copy entire PyInstaller bundle
    File /r "..\..\dist\antheneo\*.*"

    ; Start Menu shortcuts
    CreateDirectory "$SMPROGRAMS\Antheneo"
    CreateShortcut  "$SMPROGRAMS\Antheneo\Antheneo Browser.lnk" \
                    "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
    CreateShortcut  "$SMPROGRAMS\Antheneo\Uninstall Antheneo.lnk" \
                    "$INSTDIR\Uninstall.exe"

    ; Desktop shortcut (optional, user can remove)
    CreateShortcut  "$DESKTOP\Antheneo Browser.lnk" \
                    "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0

    ; Register URL handler (http, https)
    WriteRegStr HKLM "Software\Classes\AntheneoBrowser\shell\open\command" \
                "" '"$INSTDIR\${APP_EXE}" "%1"'
    WriteRegStr HKLM "Software\Classes\http\shell\open\command" \
                "" '"$INSTDIR\${APP_EXE}" "%1"'
    WriteRegStr HKLM "Software\Classes\https\shell\open\command" \
                "" '"$INSTDIR\${APP_EXE}" "%1"'

    ; Add/Remove Programs entry
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayName"          "${APP_NAME}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayVersion"       "${APP_VERSION}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "Publisher"            "${APP_PUBLISHER}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "URLInfoAbout"         "${APP_URL}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "InstallLocation"      "$INSTDIR"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "UninstallString"      "$INSTDIR\Uninstall.exe"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayIcon"          "$INSTDIR\${APP_EXE}"
    WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoModify"             1
    WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoRepair"             1

    ; Estimate installed size
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "${UNINSTALL_KEY}" "EstimatedSize" "$0"

    ; Write uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"

SectionEnd

;── Uninstaller ───────────────────────────────────────────────────────────
Section "Uninstall"
    ; Remove installed files
    RMDir /r "$INSTDIR"

    ; Remove Start Menu
    RMDir /r "$SMPROGRAMS\Antheneo"

    ; Remove Desktop shortcut
    Delete "$DESKTOP\Antheneo Browser.lnk"

    ; Remove registry entries
    DeleteRegKey HKLM "${UNINSTALL_KEY}"
    DeleteRegKey HKLM "Software\Classes\AntheneoBrowser"

    ; Offer to remove user data
    MessageBox MB_YESNO "Remove user settings and data?" IDNO skip_userdata
        RMDir /r "$APPDATA\Antheneo"
    skip_userdata:

SectionEnd
