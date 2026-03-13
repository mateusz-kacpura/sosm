# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

frontend_dist = os.path.join('frontend', 'out')

a = Analysis(
    ['launcher.py'],
    pathex=[os.path.join(os.getcwd(), 'backend')],
    binaries=[],
    datas=[
        (frontend_dist, 'frontend_dist'),
    ],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'aiosqlite',
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.dialects.sqlite.aiosqlite',
        'apscheduler',
        'apscheduler.schedulers.asyncio',
        'apscheduler.triggers.interval',
        'nodriver',
        'httpx',
        'httpx._transports',
        'httpx._transports.default',
        'app.main',
        'app.api.endpoints',
        'app.api.system_endpoints',
        'app.models',
        'app.models.models',
        'app.models.schemas',
        'app.core.config',
        'app.core.database',
        'app.core.scheduler',
        'app.task_runner',
        'app.worker',
        'app.bot.browser_manager',
        'app.bot.actions',
        'app.bot.donut_client',
        'app.bot.dom_walker',
        'app.bot.mouse_engine',
        'app.bot.fingerprint_collector',
        'app.bot.checkpoint_detector',
        'app.bot.human_imitation',
        'app.bot.donut_auto_config',
        'argon2',
        'argon2.low_level',
        'cryptography',
        'cryptography.hazmat.primitives.ciphers.aead',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'celery',
        'redis',
        'asyncpg',
        'psycopg2',
        'alembic',
    ],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SOSM',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='SOSM',
)
