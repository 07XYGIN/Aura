from __future__ import annotations

import os
from typing import Any

import requests
from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas.response import SuccessResponse

router = APIRouter(
    prefix="/api/location",
    tags=["location"],
)

AMAP_BASE_URL = "https://restapi.amap.com/v3"


@router.get("/adcode", response_model=SuccessResponse)
async def resolve_adcode(
    request: Request,
    city: str | None = Query(default=None),
    longitude: float | None = Query(default=None),
    latitude: float | None = Query(default=None),
):
    amap_key = get_amap_key()

    if city and city.strip():
        return SuccessResponse(data=resolve_by_city(amap_key, city.strip()))

    if longitude is not None and latitude is not None:
        return SuccessResponse(data=resolve_by_coordinates(amap_key, longitude, latitude))

    public_ip = resolve_public_ip(request)
    if not public_ip:
        raise HTTPException(status_code=400, detail="无法获取客户端公网 IP，请手动提供城市")

    return SuccessResponse(data=resolve_by_ip(amap_key, public_ip))


def get_amap_key() -> str:
    amap_key = os.getenv("AMAP_KEY") or os.getenv("amap_key") or ""
    if not amap_key:
        raise HTTPException(status_code=500, detail="尚未配置高德地图 API Key")
    return amap_key


def resolve_by_coordinates(amap_key: str, longitude: float, latitude: float) -> dict[str, Any]:
    if longitude < -180 or longitude > 180 or latitude < -90 or latitude > 90:
        raise HTTPException(status_code=400, detail="经纬度超出有效范围")

    data = get_amap(
        amap_key,
        "/geocode/regeo",
        {
            "location": f"{longitude},{latitude}",
            "extensions": "base",
            "radius": "1000",
        },
    )
    component = data.get("regeocode", {}).get("addressComponent", {})
    adcode = str(component.get("adcode") or "").strip()
    if not adcode:
        raise HTTPException(status_code=502, detail="高德地图没有返回城市编码")

    return {
        "adcode": adcode,
        "province": first_text(component.get("province")),
        "city": first_text(component.get("city")),
        "district": first_text(component.get("district")),
        "citycode": component.get("citycode"),
        "source": "regeo",
    }


def resolve_by_city(amap_key: str, city: str) -> dict[str, Any]:
    data = get_amap(
        amap_key,
        "/config/district",
        {
            "keywords": city,
            "subdistrict": "0",
            "extensions": "base",
        },
    )
    districts = data.get("districts") or []
    district = next((item for item in districts if item.get("adcode")), None)
    if not district:
        raise HTTPException(status_code=400, detail="没有找到对应城市编码")

    return {
        "adcode": district.get("adcode"),
        "province": district.get("name"),
        "city": district.get("name"),
        "district": district.get("name"),
        "citycode": district.get("citycode"),
        "source": "district",
    }


def resolve_by_ip(amap_key: str, public_ip: str) -> dict[str, Any]:
    data = get_amap(amap_key, "/ip", {"ip": public_ip})
    adcode = str(data.get("adcode") or "").strip()
    if not adcode:
        raise HTTPException(status_code=502, detail="高德地图没有根据 IP 返回城市编码")

    return {
        "adcode": adcode,
        "province": first_text(data.get("province")),
        "city": first_text(data.get("city")),
        "district": None,
        "citycode": None,
        "source": "ip",
    }


def get_amap(amap_key: str, path: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.get(
            f"{AMAP_BASE_URL}{path}",
            params={**params, "key": amap_key},
            timeout=8,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise HTTPException(status_code=502, detail="高德地图接口请求失败") from exc

    if data.get("status") != "1":
        raise HTTPException(
            status_code=502,
            detail=f"高德地图接口返回失败（错误码：{data.get('infocode', '未知')}）",
        )

    return data


def resolve_public_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",", 1)[0].strip()
        if is_public_ip_candidate(ip):
            return ip

    real_ip = request.headers.get("x-real-ip")
    if real_ip and is_public_ip_candidate(real_ip):
        return real_ip.strip()

    client_ip = request.client.host if request.client else None
    if client_ip and is_public_ip_candidate(client_ip):
        return client_ip

    return None


def is_public_ip_candidate(value: str) -> bool:
    if not value:
        return False
    if value.startswith(("127.", "10.", "192.168.", "172.16.", "localhost")):
        return False
    return value not in {"::1", "0.0.0.0"}


def first_text(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        return str(value[0])
    return None
