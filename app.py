from flask import Flask, render_template, request
import requests
import os
import re

app = Flask(__name__)

API_KEY = "1fbb55865e75465eb58110159252310"  # 你的 WeatherAPI Key
HEADERS = {"User-Agent": "Mozilla/5.0"}

# 英文省份/国家到中文的简单映射（常见即可，缺的可以再补）
REGION_CN = {
    "Beijing": "北京", "Tianjin": "天津", "Shanghai": "上海", "Chongqing": "重庆",
    "Hebei": "河北", "Henan": "河南", "Shandong": "山东", "Shanxi": "山西",
    "Shaanxi": "陕西", "Liaoning": "辽宁", "Jilin": "吉林", "Heilongjiang": "黑龙江",
    "Jiangsu": "江苏", "Zhejiang": "浙江", "Anhui": "安徽", "Fujian": "福建",
    "Jiangxi": "江西", "Hubei": "湖北", "Hunan": "湖南", "Guangdong": "广东",
    "Guangxi": "广西", "Hainan": "海南", "Sichuan": "四川", "Guizhou": "贵州",
    "Yunnan": "云南", "Tibet": "西藏", "Gansu": "甘肃", "Qinghai": "青海",
    "Ningxia": "宁夏", "Xinjiang": "新疆", "Inner Mongolia": "内蒙古",
    "Hong Kong": "香港", "Macau": "澳门", "Taiwan": "台湾",
}
COUNTRY_CN = {"China": "中国"}

def to_cn_region(region_en: str) -> str:
    return REGION_CN.get(region_en, region_en)

def to_cn_country(country_en: str) -> str:
    return COUNTRY_CN.get(country_en, country_en)

def best_match(candidates, query):
    """
    中文输入时的“更精准匹配”策略：
    1) 完全同名（中文/英文不区分大小写）优先
    2) 过滤出中国境内的候选；在这些中，优先 region 像“省/直辖市/自治区/特别行政区”的
    3) 否则取第一个
    """
    q_raw = query.strip()
    q = q_raw.lower()
    is_cn = bool(re.search(r"[\u4e00-\u9fff]", q_raw))

    # 1) 完全同名优先（中文或大小写不敏感英文）
    for c in candidates:
        if is_cn and c["name"] == q_raw:
            return c
        if c["name"].lower() == q:
            return c

    # 2) 在中国的候选
    in_cn = [c for c in candidates if c.get("country") in ("China", "中国")]

    if in_cn:
        # 名称包含输入（尽量同名或包含）
        name_hit = [c for c in in_cn if q in c["name"].lower()]
        pool = name_hit or in_cn

        # region 像省级行政区的优先（减少匹配到村镇）
        def is_prov_like(r: str) -> bool:
            r_cn = to_cn_region(r)
            return any(k in r_cn for k in ("省", "市", "自治区", "特别行政区"))
        prov_like = [c for c in pool if is_prov_like(c.get("region", ""))]
        if prov_like:
            return prov_like[0]
        return pool[0]

    # 3) 兜底
    return candidates[0]


@app.route("/", methods=["GET", "POST"])
def index():
    weather = None
    if request.method == "POST":
        city_input = request.form.get("city", "").strip()
        if not city_input:
            weather = {"error": "请输入城市名称（如：北京 / 上海 / 广州）。"}
        else:
            try:
                # ① 精确搜索城市
                s_url = "https://api.weatherapi.com/v1/search.json"
                sr = requests.get(s_url, params={"key": API_KEY, "q": city_input},
                                  headers=HEADERS, timeout=10)
                sdata = sr.json()
                if not isinstance(sdata, list) or not sdata:
                    weather = {"error": f"未找到与“{city_input}”匹配的城市，请检查输入。"}
                else:
                    loc_pick = best_match(sdata, city_input)

                    # ② 用匹配到的城市名再查实时天气
                    n_url = "https://api.weatherapi.com/v1/current.json"
                    nr = requests.get(n_url, params={"key": API_KEY, "q": loc_pick["name"], "lang": "zh", "aqi": "no"},
                                      headers=HEADERS, timeout=10)
                    data = nr.json()
                    if "current" not in data:
                        msg = data.get("error", {}).get("message", "查询失败，请稍后重试。")
                        weather = {"error": msg}
                    else:
                        cur = data["current"]
                        loc = data["location"]

                        region_cn = to_cn_region(loc.get("region", ""))
                        country_cn = to_cn_country(loc.get("country", ""))

                        weather = {
                            "city": f'{loc.get("name","")} {region_cn} {country_cn}'.strip(),
                            "temp": cur["temp_c"],
                            "desc": cur["condition"]["text"],
                            "humidity": cur["humidity"],
                            "wind": f'{cur["wind_dir"]} {cur["wind_kph"]} km/h',
                            "updated": cur["last_updated"],
                        }
            except Exception as e:
                weather = {"error": f"请求失败：{e}"}

    return render_template("index.html", weather=weather)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
