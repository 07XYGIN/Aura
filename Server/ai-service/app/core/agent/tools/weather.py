import logging
import os
from dotenv import load_dotenv
from langchain.tools import tool
from requests import get

load_dotenv()

@tool
def get_weather()-> dict[str, str]:
    """
        当用户主动询问天气信息时 如 "今天天气怎么样?"、”帮我查看天气“等问题时使用该tool
        根据location获取指定地点的天气,返回obj天气信息 默认为北京
        status:状态   1 请求成功 0 请求失败
        info: 信息    接口的返回信息
        city: 城市    当前用户所在城市
        province: 省份  当前用户所在省份
        weather: 天气   当前用户的天气
        temperature： 温度 当前天气的温度
        winddirection: 风向  当前风向

        不可以胡编乱造，如果该tool没有返回消息 则返回 "没有查询到当前城市的天气信息"
    """
    logging.info("命中查看天气的tool")
    params = {
        "city":110101,
        "key":os.getenv("amap_key"),
        "extensions":"base"
    }
    url = 'https://restapi.amap.com/v3/weather/weatherInfo?parameters'
    weather_result = get(url,params).json()
    city_weather = weather_result.get('lives')[0]
    status: int = weather_result["status"]
    info: str = weather_result["info"]  # 信息
    province = city_weather['province']
    city = city_weather['city']
    weather = city_weather['weather']
    temperature = city_weather['temperature']
    winddirection = city_weather['winddirection']

    return {
        "city":city,
        "status": status,
        "info": info,
        "province": province,
        "weather": weather,
        "temperature": temperature,
        "winddirection": winddirection,
    }
