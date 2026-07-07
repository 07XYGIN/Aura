from __future__ import annotations

import logging
import os

import requests
from langchain_core.tools import tool

from .logging_utils import log_tool


@tool
@log_tool
def get_weather(city_adcode: str | None = None) -> dict[str, str]:
    """按高德 adcode 查询天气；没有城市时不要猜测，先让用户补充城市。"""
    return fetch_weather(city_adcode)


def fetch_weather(city_adcode: str | None = None) -> dict[str, str]:
    if not city_adcode:
        return {
            "status": "0",
            "info": "缺少城市 adcode，不能查询或猜测天气。请先确认用户所在城市。",
        }

    logging.info("Weather tool city_adcode=%s", city_adcode)
    amap_key = os.getenv("amap_key")
    if not amap_key:
        return {
            "status": "0",
            "info": "缺少高德地图 API Key，不能提供实时天气。",
        }

    params = {
        "city": city_adcode,
        "key": amap_key,
        "extensions": "base",
    }
    url = "https://restapi.amap.com/v3/weather/weatherInfo"
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        weather_result = response.json()
    except (requests.RequestException, ValueError) as exc:
        logging.warning("Weather API request failed: %s", exc)
        return {
            "status": "0",
            "info": "没有查询到当前城市的天气信息。",
        }

    lives = weather_result.get("lives") or []
    if weather_result.get("status") != "1" or not lives:
        return {
            "status": weather_result.get("status", "0"),
            "info": weather_result.get("info", "没有查询到当前城市的天气信息。"),
        }

    city_weather = lives[0]
    return {
        "city": city_weather.get("city", ""),
        "status": weather_result.get("status", ""),
        "info": weather_result.get("info", ""),
        "province": city_weather.get("province", ""),
        "weather": city_weather.get("weather", ""),
        "temperature": city_weather.get("temperature", ""),
        "winddirection": city_weather.get("winddirection", ""),
    }
