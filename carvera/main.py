import asyncio
import advertiser
import proxy


async def main():
    await asyncio.gather(advertiser.main(), proxy.main())


if __name__ == "__main__":
    asyncio.run(main())
