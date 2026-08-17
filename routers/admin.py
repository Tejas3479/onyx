from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from auth import verify_api_key
from database import Proxy, async_session_maker
from models import ProxyCreate

router = APIRouter(tags=["admin"])


@router.post("/api/proxies", dependencies=[Depends(verify_api_key)])
async def add_proxy(proxy: ProxyCreate):
    async with async_session_maker() as session:
        result = await session.execute(select(Proxy).where(Proxy.url == proxy.url))
        existing = result.scalars().first()
        if existing:
            return {"status": "already_exists", "id": existing.id}

        new_proxy = Proxy(url=proxy.url)
        session.add(new_proxy)
        await session.commit()
        await session.refresh(new_proxy)
        return {"status": "added", "id": new_proxy.id}


@router.get("/api/proxies", dependencies=[Depends(verify_api_key)])
async def list_proxies():
    async with async_session_maker() as session:
        result = await session.execute(select(Proxy))
        proxies = result.scalars().all()
        return [
            {
                "id": p.id,
                "url": p.url,
                "is_active": p.is_active,
                "fail_count": p.fail_count,
            }
            for p in proxies
        ]


@router.delete("/api/proxies/{proxy_id}", dependencies=[Depends(verify_api_key)])
async def delete_proxy(proxy_id: str):
    async with async_session_maker() as session:
        result = await session.execute(select(Proxy).where(Proxy.id == proxy_id))
        proxy = result.scalars().first()
        if not proxy:
            raise HTTPException(status_code=404, detail="Proxy not found")

        await session.delete(proxy)
        await session.commit()
        return {"status": "deleted"}
