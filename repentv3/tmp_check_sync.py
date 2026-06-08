
import asyncio
from main import Repent

async def run():
    b = Repent()
    await b.setup_hook()
    print('Loaded cogs:', sorted(b.extensions.keys()))
    try:
        await b.tree.sync()
        print('Sync complete')
    except Exception as e:
        print('Sync error:', repr(e))
    await b.close()

asyncio.run(run())
