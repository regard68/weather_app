from flask import Flask, render_template, request
import requests, os, re

app = Flask(__name__)

# 优先用环境变量（更安全），没有就用占位符字符串
API_KEY = os.getenv("WEATHER_API_KEY", "YOUR_API_KEY")
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

# 一些“拼音 → 英文城市名”的兜底映射（不全，常见特例先覆盖）
PINYIN_TO_EN = {
    "haerbin": "Harbin",          # 哈尔滨
    "xian": "Xi'an",              # 西安
    "urumqi": "Ürümqi",           # 乌鲁木齐（英文常用 Urumqi/Ürümqi）
    "wulumuqi": "Ürümqi",
    "huhehaote": "Hohhot",        # 呼和浩特
    "guiyang": "Guiyang",
    "guangzhou": "Guangzhou",
    "hangzhou": "Hangzhou",
    "nanjing": "Nanjing",
    "shenyang": "Shenyang",
    "changchun": "Changchun",
    "changsha": "Changsha",
    "chengdu": "Chengdu",
    "chongqing": "Chongqing",
    "beijing": "Beijing",
    "tianjin": "Tianjin",
    "shanghai": "Shanghai",
    "xuzhou": "Xuzhou",
    "weifang": "Weifang",
    "qingdao": "Qingdao",
    "jinan": "Jinan",
    "wuhan": "Wuhan",
    "zhengzhou": "Zhengzhou",
    "taiyuan": "Taiyuan",
    "xining": "Xining",
    "ningbo": "Ningbo",
    "kunming": "Kunming",
    "lanzhou": "Lanzhou",
    "baotou": "Baotou",
    "fuzhou": "Fuzhou",
    "xiamen": "Xiamen",
    "haikou": "Haikou",
    "sanya": "Sanya",
}

def normalize_query(raw: str) -> str:
    """把用户输入规范化：
       - 如果是纯拼音(a-z/空格/连字符)，尝试做特例映射，否则直接用原拼音
       - 一律在查询时加上 'China' 以限定在中国
    """
    s = (raw or "").strip()
    if not s:
        return ""

    # 纯英文/拼音？
    if re.fullmatch(r"[a-zA-Z\s\-'.]+", s):
        key = s.lower().replace(" ", "").replace("-", "")
        # 特例映射（如 haerbin -> Harbin）
        if key in PINYIN_TO_EN:
            return PINYIN_TO_EN[key] + ", China"
        # 有些需要加撇或大小写的：尝试几种常见变体
        if key == "xian":
            return "Xi'an, China"
        # 默认直接用原始输入（WeatherAPI 对常见城市英文/拼音较友好）
        return s + ", China"

    # 含有中文就直接原样 + China 限定
    return s + ", China"

@app.route("/", methods=["GET", "POST"])
def index():
    weather = None
    hint = "请输入城市拼音（或中文），例如：beijing / shanghai / weifang / haerbin / 西安 / 潍坊"

    if request.method == "POST":
        raw = request.form.get("city", "").strip()
        q = normalize_query(raw)

        if not q:
            weather = {"error": hint}
        else:
            try:
                # 1) search：限定在 China（normalize_query 已加 , China）
                s_url = "https://api.weatherapi.com/v1/search.json"
                resp = requests.get(s_url, params={"key": API_KEY, "q": q}, headers=HEADERS, timeout=10)
                items = resp.json()
                if not isinstance(items, list) or not items:
                    weather = {"error": f"未找到：{raw}。{hint}"}
                else:
                    # 只取 country 为 China 的第一个
                    pick = next((c for c in items if c.get("country") in ("China", "中国")), None)
                    if not pick:
                        weather = {"error": f"未匹配到中国境内城市：{raw}。{hint}"}
                    else:
                        # 2) 用挑中的城市查实时天气
                        n_url = "https://api.weatherapi.com/v1/current.json"
                        r2 = requests.get(
                            n_url,
                            params={"key": API_KEY, "q": pick["name"], "lang": "zh", "aqi": "no"},
                            headers=HEADERS,
                            timeout=10,
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
                                "wind": f"{cur.get('wind_dir','')} {cur.get('wind_kph','')} km/h".strip(),
                                "updated": cur.get("last_updated"),
                            }
            except Exception as e:
                weather = {"error": f"请求失败：{e}"}

    return render_template("index.html", weather=weather, hint=hint)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
