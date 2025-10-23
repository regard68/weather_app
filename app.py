from flask import Flask, render_template, request
import requests

app = Flask(__name__)

API_KEY = "1fbb55865e75465eb58110159252310"

@app.route("/", methods=["GET", "POST"])
def index():
    weather = None
    if request.method == "POST":
        city = request.form.get("city", "").strip()
        if not city:
            weather = {"error": "请输入城市名称（如：北京、上海、广州）"}
        else:
            url = f"https://api.weatherapi.com/v1/current.json"
            params = {
                "key": API_KEY,
                "q": city,
                "lang": "zh",
                "aqi": "no"
            }
            try:
                r = requests.get(url, params=params, timeout=10)
                data = r.json()
                # 判断是否成功
                if "current" in data:
                    loc = data["location"]
                    cur = data["current"]
                    weather = {
                        "city": loc["name"],
                        "temp": cur["temp_c"],
                        "desc": cur["condition"]["text"],
                        "humidity": cur["humidity"],
                        "wind": f'{cur["wind_dir"]} {cur["wind_kph"]} km/h',
                        "update": cur["last_updated"]
                    }
                else:
                    # 返回错误结构
                    weather = {"error": data.get("error", {}).get("message", "查询失败")}
            except Exception as e:
                weather = {"error": f"请求失败：{e}"}
    return render_template("index.html", weather=weather)

if __name__ == "__main__":
    app.run(debug=True)
