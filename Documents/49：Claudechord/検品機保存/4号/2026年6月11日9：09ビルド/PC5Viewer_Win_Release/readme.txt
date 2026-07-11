PC5 Viewer  -  Quick Start Guide
=================================================
Version 2.3  |  Windows 10 / 11 (64-bit)
Python / Node.js installation NOT required
=================================================

[Installation]
  1. Right-click "install.bat"
  2. Select "Run as administrator"
  3. Double-click "PC5Viewer" on the Desktop

[First launch warning]
  If Windows shows "Windows protected your PC":
    Click "More info" -> "Run anyway"

[Opening PC5 files]
  1. Click [Browse...] button
  2. Select drive or network folder
     Example: Z:\InspectionData\Machine4
  3. Check multiple folders to load together
  4. Click [Open selected]
  * Only files WITH defects are listed

[Display period]
  Use the period selector (7 days / 30 days / All)
  First load is fast (7 days default)
  Cache speeds up subsequent loads automatically

[Network access from other PCs]
  After launch, the console shows:
    http://192.168.x.x:8765
  Open this URL on any browser in the same network

[Uninstall]
  Control Panel -> Programs -> PC5 Viewer -> Uninstall

[Troubleshooting]
  - Browser does not open:
      Open http://localhost:8765 manually
  - Port already in use:
      End "PC5Viewer.exe" in Task Manager, then restart
  - viewer.html not found:
      Ensure PC5Viewer.exe and viewer.html are in the same folder
  - Product names not showing / data empty (old version):
      Delete %TEMP%\pc5viewer_cache.json and restart
      (v2.3 fixes this automatically)

=================================================
Recommended browsers: Google Chrome / Microsoft Edge
=================================================
