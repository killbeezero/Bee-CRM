# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('credentials.json', '.')],
    hiddenimports=[
        'google.auth',
        'google.oauth2',
        'google_auth_oauthlib',
        'googleapiclient',
        'reportlab',
        'playwright.sync_api',
        'PyQt6',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='蜜蜂CRM',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    name='蜜蜂CRM.app',
    icon=None,
    bundle_identifier='com.beecrm.app',
    info_plist={
        'NSHighResolutionCapable': True,
        'CFBundleDisplayName': '蜜蜂CRM',
    },
)
