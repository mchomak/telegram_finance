"""Quick proxy check — run on the server: python check_proxy.py"""
import asyncio
import aiohttp
from aiohttp_socks import ProxyConnector

PROXY = "socks5://tg1132147659_1777165894:EJ9Xi9IbmtTITFuj@144.31.122.115:443"
TEST_URL = "https://api.telegram.org"


async def main() -> None:
    print(f"Proxy : {PROXY}")
    print(f"Target: {TEST_URL}")
    print("-" * 40)

    # 1. Raw TCP connect to proxy host
    print("1) TCP connect to proxy host...", end=" ", flush=True)
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection("144.31.122.115", 443), timeout=10
        )
        writer.close()
        await writer.wait_closed()
        print("OK")
    except Exception as e:
        print(f"FAIL — {e}")
        print("   Proxy host is unreachable. Check IP/port or firewall.")
        return

    # 2. HTTP request through proxy
    print("2) GET through SOCKS5 proxy...", end=" ", flush=True)
    try:
        connector = ProxyConnector.from_url(PROXY)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(TEST_URL, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                print(f"OK — HTTP {resp.status}")
    except Exception as e:
        print(f"FAIL — {e}")


asyncio.run(main())
