from urllib.parse import quote_plus
import requests
import feedparser
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
import datetime
from functools import wraps

app = Flask(__name__)

# ---------------- SQL (SQLite) ----------------
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///history.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)





def decorator(func):
    @wraps(func)
    def wraper(*args,**kwargs):
        start_time=datetime.datetime.now()
        A=func(*args,**kwargs)
        finish_time=datetime.datetime.now()
        total=finish_time-start_time
        print(total)
        return A
    return wraper



class SearchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    search_type = db.Column(db.String(20), nullable=False)  # "weather" or "news"
    query = db.Column(db.String(100), nullable=False)


with app.app_context():
    db.create_all()


# ---------------- Routes ----------------
@app.route("/")
def home():
    # default tab = weather
    return render_template("index.html", active_tab="weather")


@app.route("/weather", methods=["POST"])
@decorator
def weather():
    city = (request.form.get("city") or "").strip()

    if not city:
        return render_template("index.html",
                               weather_result="<b>Error:</b> Please enter a city.",
                               active_tab="weather")

    # Save search to DB
    db.session.add(SearchHistory(search_type="weather", query=city))
    db.session.commit()

    # 1) City -> Lat/Lon (Open-Meteo Geocoding) with fallback
    geo_url = "https://geocoding-api.open-meteo.com/v1/search"
    candidates = [city, f"{city}, Delhi", f"{city}, New Delhi", "New Delhi"]

    place = None
    for q in candidates:
        geo_res = requests.get(geo_url, params={"name": q, "count": 1}, timeout=20)
        geo_data = geo_res.json()
        if geo_data.get("results"):
            place = geo_data["results"][0]
            break

    if not place:
        return render_template(
            "index.html",
            weather_result=f"<b>Error:</b> City not found: {city}. Try: <i>RK Puram, Delhi</i>",
            active_tab="weather"
        )

    lat = place["latitude"]
    lon = place["longitude"]
    full_name = f'{place.get("name")}, {place.get("admin1", "")}, {place.get("country", "")}'.strip(", ")

    # 2) Lat/Lon -> Weather (Open-Meteo Forecast)
    weather_url = "https://api.open-meteo.com/v1/forecast"
    w_res = requests.get(
        weather_url,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,wind_speed_10m,relative_humidity_2m",
            "timezone": "auto",
            "hourly": ["temperature_2m", "relative_humidity_2m", "dew_point_2m", "apparent_temperature", "precipitation_probability", "cloud_cover_low", "cloud_cover", "surface_pressure", "pressure_msl", "vapour_pressure_deficit", "evapotranspiration", "wind_direction_180m", "wind_speed_80m", "wind_speed_10m"],

        },
        timeout=20
    )
    

    w_data = w_res.json()
    current = w_data.get("current") or {}

    temp = current.get("temperature_2m")
    wind = current.get("wind_speed_10m")
    humidity = current.get("relative_humidity_2m")
    
    result_html = (
        f"<b>Weather for:</b> {full_name} ✅<br>"
        f"<b>Temperature:</b> {temp}°C<br>"
        f"<b>Wind:</b> {wind} km/h<br>"
        f"<b>Humidity:</b> {humidity}%"
    )

    return render_template("index.html", weather_result=result_html, active_tab="weather")



@app.route("/news", methods=["POST"])
@decorator
def news():
    topic = (request.form.get("topic") or "").strip()

    if not topic:
        return render_template("index.html",
                               news_result="<b>Error:</b> Please enter a topic.",
                               active_tab="news")

    # Save search to DB
    db.session.add(SearchHistory(search_type="news", query=topic))
    db.session.commit()

    url = f"https://news.google.com/rss/search?q={quote_plus(topic)}&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(url)

    if not feed.entries:
        return render_template("index.html", news_result="<b>No news found.</b>", active_tab="news")

    news_html = "<ul>"
    for entry in feed.entries[:5]:
        news_html += f'<li><a href="{entry.link}" target="_blank">{entry.title}</a></li>'
    news_html += "</ul>"

    return render_template("index.html", news_result=news_html, active_tab="news")
@app.route("/history")
def history():
    records = db.session.query(SearchHistory)\
    .order_by(SearchHistory.id.desc())\
    .limit(10)\
    .all()

    return render_template("index.html", history=records, active_tab="history")

if __name__ == "__main__":
    app.run(debug=True)
