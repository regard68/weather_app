from flask import Flask, render_template, request
import requests, os, re

app = Flask(__name__)

# 直接写入固定的 API Key（不要用 os.getenv）
API_KEY = "1fbb55865e75465eb58110159252310"  # ← 把这行改成你自己的 key
HEADERS = {"User-Agent": "Mozilla/5.0"}

# 英文省份/直辖市 -> 中文
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
COUNTRY_CN = {"China": "中国", "中国": "中国"}

def to_cn_region(region_en: str) -> str:
    return REGION_CN.get(region_en, region_en or "")

def to_cn_country(country: str) -> str:
    return COUNTRY_CN.get(country, country or "")

@app.route("/", methods=["GET", "POST"])
def index():
    weather = None
    hint = "请输入完整的“省份 市名”，例如：山东 潍坊 / 黑龙江 哈尔滨 / 北京 北京"

    if request.method == "POST":
        raw = request.form.get("city", "").strip()
        if not raw:
            weather = {"error": hint}
        else:
            try:
                # 1. 搜索城市
                s_url = "https://api.weatherapi.com/v1/search.json"
                resp = requests.get(s_url, params={"key": API_KEY, "q": raw}, headers=HEADERS, timeout=10)
                items = resp.json()

                if not isinstance(items, list) or not items:
                    weather = {"error": f"未找到：{raw}。{hint}"}
                else:
                    # 只取中国境内的第一个匹配
                    pick = next((c for c in items if c.get("country") in ("China", "中国")), None)
                    if not pick:
                        weather = {"error": f"未匹配到中国境内城市：{raw}。{hint}"}
                    else:
                        # 2. 查实时天气
                        n_url = "https://api.weatherapi.com/v1/current.json"
                        r2 = requests.get(
                            n_url,
                            params={"key": API_KEY, "q": pick["name"], "lang": "zh", "aqi": "no"},
                            headers=HEADERS, timeout=10
                        )
                        data = r2.json()
                        if "current" not in data:
                            msg = data.get("error", {}).get("message", "查询失败，请稍后重试。")
                            weather = {"error": msg}
                        else:
                            cur = data["current"]
                            prov_cn = to_cn_region(pick.get("region", ""))
                            country_cn = to_cn_country(pick.get("country", ""))
                            weather = {
                                "city": f"{prov_cn} {pick['name']} {country_cn}".strip(),
                                "temp": cur.get("temp_c"),
                                "desc": cur.get("condition", {}).get("text", ""),
                                "humidity": cur.get("humidity"),
                                "wind": f"{cur.get('wind_dir','')} {cur.get('wind_kph','')} km/h",
                                "updated": cur.get("last_updated"),
                            }
            except Exception as e:
                weather = {"error": f"请求失败：{e}"}

    return render_template("index.html", weather=weather, hint=hint)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
