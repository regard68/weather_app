from flask import Flask, render_template, request
import requests
import os
import re

app = Flask(__name__)

API_KEY = "1fbb55865e75465eb58110159252310"  # 你的 WeatherAPI Key

HEADERS = {"User-Agent": "Mozilla/5.0"}

def best_match(candidates, query):
    """
    从 WeatherAPI search.json 返回的候选城市里挑一个最合适的：
    1) 完全等于城市名（中文/英文）
    2) 国家是中国且名称包含输入
    3) 否则取第一个
    """
    q = query.strip().lower()
    is_chinese = bool(re.search(r"[\u4e00-\u9fff]", q))

    # 完全相等优先
    for c in candidates:
        if c["name"].lower() == q or (is_chinese and c["name"] == query):
            return c

    # 其次：国家为中国并且名字或地区包含查询
    for c in candidates:
        if c.get("country") in ("中国", "China"):
            if q in c["name"].lower() or q in c.get("region", "").lower():
                return c

    # 兜底：第一个
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
                # ① 先精确搜索城市
                search_url = "https://api.weatherapi.com/v1/search.json"
                sr = requests.get(
                    search_url,
                    params={"key": API_KEY, "q": city_input},
                    headers=HEADERS,
                    timeout=10
                )
                sdata = sr.json()
                if not isinstance(sdata, list) or len(sdata) == 0:
                    weather = {"error": f"未找到与“{city_input}”匹配的城市，请检查输入。"}
                else:
                    loc = best_match(sdata, city_input)
                    # ② 用匹配到的城市再查实时天气
                    now_url = "https://api.weatherapi.com/v1/current.json"
                    nr = requests.get(
                        now_url,
                        params={"key": API_KEY, "q": loc["name"], "lang": "zh", "aqi": "no"},
                        headers=HEADERS,
                        timeout=10
                    )
                    data = nr.json()
                    if "current" not in data:
                        msg = data.get("error", {}).get("message", "查询失败，请稍后重试。")
                        weather = {"error": msg}
                    else:
                        cur = data["current"]
                        loc_full = data["location"]
                        weather = {
                            "city": f'{loc_full["name"]} {loc_full.get("region","")} {loc_full.get("country","")}'.strip(),
                            "temp": cur["temp_c"],
                            "desc": cur["condition"]["text"],
                            "humidity": cur["humidity"],
                            "wind": f'{cur["wind_dir"]} {cur["wind_kph"]} km/h',
                            "updated": cur["last_updated"],   # 用 updated，避免与 dict.update 冲突
                        }
            except Exception as e:
                weather = {"error": f"请求失败：{e}"}

    return render_template("index.html", weather=weather)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render 会注入 PORT
    app.run(host="0.0.0.0", port=port)
