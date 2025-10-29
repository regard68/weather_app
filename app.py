from flask import Flask, render_template, request
import requests, os, re

app = Flask(__name__)

# ✅ 直接写入 WeatherAPI Key（不要再用环境变量）
API_KEY = "1fbb55865e75465eb58110159252310"  # ← 请改成你自己的 key
HEADERS = {"User-Agent": "Mozilla/5.0"}

@app.route("/", methods=["GET", "POST"])
def index():
    weather = None
    hint = "请输入城市拼音或英文（例如：beijing / shanghai / xian / chengdu）"

    if request.method == "POST":
        city = request.form.get("city", "").strip()
        if not city:
            weather = {"error": hint}
        else:
            try:
                # ✅ 拼音或英文输入，自动限定在中国
                query = f"{city}, China"

                # 1️⃣ 搜索城市
                s_url = "https://api.weatherapi.com/v1/search.json"
                resp = requests.get(s_url, params={"key": API_KEY, "q": query}, headers=HEADERS, timeout=10)
                items = resp.json()

                if not isinstance(items, list) or not items:
                    weather = {"error": f"未找到：{city}。{hint}"}
                else:
                    # 取第一个匹配到的中国城市
                    pick = next((c for c in items if c.get("country") in ("China", "中国")), None)
                    if not pick:
                        weather = {"error": f"未匹配到中国境内城市：{city}。{hint}"}
                    else:
                        # 2️⃣ 查询实时天气
                        n_url = "https://api.weatherapi.com/v1/current.json"
                        r2 = requests.get(
                            n_url,
                            params={"key": API_KEY, "q": pick["name"], "lang": "zh", "aqi": "no"},
                            headers=HEADERS, timeout=10,
                        )
                        data = r2.json()
                        if "current" not in data:
                            msg = data.get("error", {}).get("message", "查询失败，请稍后重试。")
                            weather = {"error": msg}
                        else:
                            cur = data["current"]
                            weather = {
                                "city": f"{pick['name']} ({pick['region']}, {pick['country']})",
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
