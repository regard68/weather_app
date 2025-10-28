from flask import Flask, render_template, request
import requests, os, re

app = Flask(__name__)

API_KEY = "YOUR_API_KEY"  # 在这里替换为你自己的API Key
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

MUNICIPALITIES = {"北京", "天津", "上海", "重庆"}

def to_cn_region(region_en: str) -> str:
    return REGION_CN.get(region_en, region_en or "")

def to_cn_country(country: str) -> str:
    return COUNTRY_CN.get(country, country or "")

def norm_cn(s: str) -> str:
    """去掉常见后缀与空白做匹配"""
    if not s:
        return ""
    s = s.strip().lower()
    for suf in ["省", "市", "地区", "盟", "区", "县", "自治州", "自治区", "特别行政区"]:
        s = s.replace(suf, "")
    s = s.replace(" ", "")
    return s

def parse_input(s: str):
    """要求输入“省份 市名”，或直辖市“北京 北京”这种。支持空格/全角空格/逗号分隔。"""
    s = (s or "").strip()
    if not s:
        return None, None
    parts = re.split(r"[,\s，、]+", s)
    if len(parts) < 2:
        return None, None
    prov, city = parts[0], parts[1]
    return prov, city

def pick_city_in_china(prov_in: str, city_in: str, candidates: list):
    """从 search.json 候选中：限定中国；省+市双匹配（中文），减少跳错县镇。"""
    prov_n = norm_cn(prov_in)
    city_n = norm_cn(city_in)

    # 只保留中国
    cn_list = [c for c in candidates if c.get("country") in ("China", "中国")]
    if not cn_list:
        return None

    # 先把候选的省份转中文后再做省/市匹配
    def region_cn(c):
        return to_cn_region(c.get("region", ""))

    # 完整匹配（省包含 & 市名相等/包含）
    strong = [
        c for c in cn_list
        if prov_n in norm_cn(region_cn(c)) and
           (norm_cn(c["name"]) == city_n or city_n in norm_cn(c["name"]))
    ]
    if strong:
        return strong[0]

    # 次匹配：只要省份能对上
    by_prov = [c for c in cn_list if prov_n in norm_cn(region_cn(c))]
    if by_prov:
        # 里边优先市级（region含“省/市/自治区/特别行政区”）
        def score(c):
            r = region_cn(c)
            if any(k in r for k in ("省", "自治区", "特别行政区")): return 3
            if "市" in r: return 2
            return 1
        by_prov.sort(key=score, reverse=True)
        return by_prov[0]

    # 再次兜底：只要市名近似 + 在中国
    by_city = [c for c in cn_list if city_n in norm_cn(c["name"])]
    if by_city:
        return by_city[0]

    # 最后兜底
    return cn_list[0]

@app.route("/", methods=["GET", "POST"])
def index():
    weather = None
    hint = "请输入完整的“省份 市名”，例如：山东 潍坊 / 黑龙江 哈尔滨 / 北京 北京"

    if request.method == "POST":
        raw = request.form.get("city", "").strip()
        prov_in, city_in = parse_input(raw)

        if not prov_in or not city_in:
            weather = {"error": hint}
        else:
            try:
                # 1) 搜索（先按市名搜，再结合省筛选）
                s_url = "https://api.weatherapi.com/v1/search.json"
                resp = requests.get(s_url,
                                    params={"key": API_KEY, "q": city_in},
                                    headers=HEADERS, timeout=10)
                items = resp.json()
                if not isinstance(items, list) or not items:
                    weather = {"error": f"未找到：{raw}。{hint}"}
                else:
                    pick = pick_city_in_china(prov_in, city_in, items)
                    if not pick:
                        weather = {"error": f"未匹配到中国境内城市：{raw}。{hint}"}
                    else:
                        # 2) 用挑中的城市查实时天气
                        n_url = "https://api.weatherapi.com/v1/current.json"
                        r2 = requests.get(n_url,
                                          params={"key": API_KEY, "q": pick["name"], "lang": "zh", "aqi": "no"},
                                          headers=HEADERS, timeout=10)
                        data = r2.json()
                        if "current" not in data:
                            msg = data.get("error", {}).get("message", "查询失败，请稍后重试。")
                            weather = {"error": msg}
                        else:
                            cur = data["current"]
                            # 展示顺序：省份 -> 市
                            prov_cn = to_cn_region(pick.get("region", ""))
                            country_cn = to_cn_country(pick.get("country", ""))

                            weather = {
                                "city": f"{prov_cn} {pick['name']} {country_cn}".strip(),
                                "temp": cur["temp_c"],
                                "desc": cur["condition"]["text"],
                                "humidity": cur["humidity"],
                                "wind": f'{cur["wind_dir"]} {cur["wind_kph"]} km/h',
                                "updated": cur["last_updated"],
                            }
            except Exception as e:
                weather = {"error": f"请求失败：{e}"}

    return render_template("index.html", weather=weather, hint=hint)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
