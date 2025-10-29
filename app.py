from flask import Flask, render_template, request
import requests
import os

app = Flask(__name__)

# 直接读常量（你要求不走环境变量）。把下面字符串替换成你自己的 WeatherAPI Key
API_KEY = "1fbb55865e75465eb58110159252310"   # ←←← 在这里填你的 Key（例如：abc123...）

HEADERS = {"User-Agent": "Mozilla/5.0"}
SEARCH_URL = "https://api.weatherapi.com/v1/search.json"
CURRENT_URL = "https://api.weatherapi.com/v1/current.json"


def safe_get_json(url, params, timeout=10):
    """
    GET 并尽量安全地解析 JSON；任何异常都抛回给上层，由上层统一转成友好错误。
    """
    resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.json()  # 如果不是 JSON，会在这里抛 ValueError


@app.route("/", methods=["GET", "POST"])
def index():
    weather = None
    hint = "Enter a city in English, e.g. shanghai / beijing / tokyo"

    if request.method == "POST":
        city = (request.form.get("city") or "").strip()

        # 1) 基础校验
        if not city:
            weather = {"error": hint}
            return render_template("index.html", weather=weather, hint=hint)

        # 2) API Key 校验（防止 500）
        if not API_KEY or API_KEY.strip().upper() in {"YOUR_API_KEY", "YOUR_API_KEY_HERE", "你的WEATHERAPI_KEY"}:
            weather = {"error": "未检测到有效的 WeatherAPI Key，请在 app.py 中把 API_KEY 替换为你的 Key。"}
            return render_template("index.html", weather=weather, hint=hint)

        try:
            # 3) 先用城市英文名做搜索（全球范围，不限制中国）
            items = safe_get_json(SEARCH_URL, {"key": API_KEY, "q": city})

            if not isinstance(items, list) or not items:
                weather = {"error": f"未找到：{city}。请换一个英文城市名（例如：shanghai / beijing / tokyo）。"}
                return render_template("index.html", weather=weather, hint=hint)

            # 4) 选第一个候选（通常是最相关的）
            pick = items[0]
            # 用经纬度查询最稳妥，避免同名城市歧义
            lat = pick.get("lat")
            lon = pick.get("lon")
            q_for_current = f"{lat},{lon}" if lat is not None and lon is not None else pick.get("name")

            # 5) 查当前天气（中文描述；如需英文把 lang 改成 'en'）
            data = safe_get_json(CURRENT_URL, {"key": API_KEY, "q": q_for_current, "lang": "zh", "aqi": "no"})
            if "current" not in data:
                msg = (data.get("error") or {}).get("message", "查询失败，请稍后再试。")
                weather = {"error": msg}
                return render_template("index.html", weather=weather, hint=hint)

            cur = data["current"]
            location_line = f"{pick.get('name', '')} / {pick.get('region', '')} / {pick.get('country', '')}".strip(" /")

            weather = {
                "city": location_line,
                "temp": cur.get("temp_c"),
                "desc": (cur.get("condition") or {}).get("text", ""),
                "humidity": cur.get("humidity"),
                "wind": f"{cur.get('wind_dir', '')} {cur.get('wind_kph', '')} km/h".strip(),
                "updated": cur.get("last_updated"),
            }

        except requests.HTTPError as e:
            # HTTP 层面的错误（4xx/5xx），给用户友好提示
            weather = {"error": f"请求失败（HTTP {e.response.status_code}）。请稍后重试或检查 API Key。"}
        except ValueError:
            # 非 JSON 响应
            weather = {"error": "服务返回的格式不是 JSON，可能是 API Key 或请求参数有误。"}
        except Exception as e:
            # 其它未知异常，避免 500
            weather = {"error": f"请求失败：{e}"}

    return render_template("index.html", weather=weather, hint=hint)


if __name__ == "__main__":
    # 本地运行：python3 app.py
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
