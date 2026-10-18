// Dashboard logic: calls the API and draws the charts. Served by the same FastAPI app.

const charts = {};   // keeps the chart objects so that they can be replaced on update

const dateInput = document.getElementById("date-input");
const targetSelect = document.getElementById("target-select");
const intervalSelect = document.getElementById("interval-select");
const messageBox = document.getElementById("message");

const TARGET_NAMES = { Total_Load: "Total load", F1: "Feeder F1", F2: "Feeder F2", F3: "Feeder F3" };


async function getJson(path) {
  const response = await fetch(path);
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail || "Request failed");
  }
  return body;
}

function formatKw(value) {
  return value === null ? "-" : Math.round(value).toLocaleString("en-IN");
}

function timeLabel(timestamp) {
  return timestamp.slice(11, 16);   // "2017-12-31T17:30" -> "17:30"
}

function drawChart(id, config) {
  if (charts[id]) {
    charts[id].destroy();           // remove the old chart before drawing a new one
  }
  charts[id] = new Chart(document.getElementById(id), config);
}


// ---------------------------------------------------------------- forecast
function renderKpis(forecast) {
  const s = forecast.summary;
  document.getElementById("kpi-peak").textContent = formatKw(s.peak_kw) + " kW";
  document.getElementById("kpi-peak-time").textContent = "at " + s.peak_time;
  document.getElementById("kpi-low").textContent = formatKw(s.lowest_kw) + " kW";
  document.getElementById("kpi-low-time").textContent = "at " + s.lowest_time;
  document.getElementById("kpi-avg").textContent = formatKw(s.average_kw);
  document.getElementById("kpi-mape").textContent = forecast.model_test_mape_pct + " %";

  const badge = document.getElementById("mode-badge");
  if (forecast.mode === "forecast") {
    badge.textContent = "Live forecast";
    badge.className = "badge forecast";
  } else {
    badge.textContent = "Backtest (actual load known, day error " + s.day_mape_pct + " %)";
    badge.className = "badge backtest";
  }
}

function renderForecastChart(forecast, holidays) {
  const labels = forecast.forecast.map(row => timeLabel(row.timestamp));
  const datasets = [{
    label: "Forecast (kW)",
    data: forecast.forecast.map(row => row.forecast_kw),
    borderColor: "#1f6feb",
    backgroundColor: "rgba(31, 111, 235, 0.1)",
    fill: true,
    borderWidth: 2,
    pointRadius: 0,
    tension: 0.3,
  }];

  if (forecast.mode === "backtest") {
    datasets.push({
      label: "Actual (kW)",
      data: forecast.forecast.map(row => row.actual_kw),
      borderColor: "#6b7280",
      borderDash: [6, 4],
      borderWidth: 2,
      pointRadius: 0,
      tension: 0.3,
    });
  }

  const todaysHolidays = holidays.holidays.filter(h => h.on_forecast_date).map(h => h.holiday);
  const title = TARGET_NAMES[forecast.target] + " on " + forecast.date +
    (todaysHolidays.length ? "  |  Holiday: " + todaysHolidays.join(", ") : "");
  document.getElementById("forecast-title").textContent = title;
  document.getElementById("forecast-note").textContent = forecast.note;

  drawChart("forecast-chart", {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { ticks: { maxTicksLimit: 12 }, title: { display: true, text: "Time of day" } },
        y: { title: { display: true, text: "Power (kW)" } },
      },
    },
  });
}


// ----------------------------------------------------------------- weather
function weatherChart(id, label, values, labels, color, type) {
  drawChart(id, {
    type: type,
    data: {
      labels,
      datasets: [{
        label,
        data: values,
        borderColor: color,
        backgroundColor: color,
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.3,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, title: { display: true, text: label } },
      scales: { x: { ticks: { maxTicksLimit: 6 } } },
    },
  });
}

function renderWeather(weather) {
  const rows = weather.weather;
  const labels = rows.map(row => timeLabel(row.timestamp));
  weatherChart("temp-chart", "Temperature (°C)", rows.map(r => r.temperature_c), labels, "#dc2626", "line");
  weatherChart("humidity-chart", "Relative humidity (%)", rows.map(r => r.humidity_pct), labels, "#0891b2", "line");
  weatherChart("cloud-chart", "Cloud cover (%)", rows.map(r => r.cloud_cover_pct), labels, "#6b7280", "bar");

  const s = weather.summary;
  document.getElementById("weather-note").textContent =
    "Temperature " + s.temperature_min_c + " to " + s.temperature_max_c + " °C, average humidity " +
    s.humidity_avg_pct + " %, average cloud cover " + s.cloud_cover_avg_pct + " %. Source: " + weather.source + ".";
}


// ---------------------------------------------------------------- holidays
function relativeText(days) {
  if (days === 0) return "Forecast day";
  if (days > 0) return "in " + days + " day" + (days > 1 ? "s" : "");
  return Math.abs(days) + " day" + (days < -1 ? "s" : "") + " ago";
}

function renderHolidays(holidays) {
  const body = document.getElementById("holiday-body");
  body.innerHTML = "";

  holidays.holidays.forEach(h => {
    const row = document.createElement("tr");
    if (h.on_forecast_date) {
      row.className = "today";
    }
    [h.date, h.weekday, h.holiday, h.category, relativeText(h.days_from_forecast_date)].forEach((text, i) => {
      const cell = document.createElement("td");
      if (i === 3) {
        cell.innerHTML = '<span class="tag">' + text + "</span>";
      } else {
        cell.textContent = text;
      }
      row.appendChild(cell);
    });
    body.appendChild(row);
  });

  const note = document.getElementById("holiday-note");
  if (holidays.holidays.length === 0) {
    note.textContent = "No holidays within " + holidays.window_days + " days of " + holidays.date + ".";
  } else {
    note.textContent = (holidays.is_holiday ? "The forecast day is a holiday. " : "The forecast day is a normal day. ") +
      "Showing holidays within " + holidays.window_days + " days.";
  }
}


// -------------------------------------------------------------------- main
async function loadDashboard() {
  messageBox.textContent = "";
  const date = dateInput.value;
  const target = targetSelect.value;
  const interval = intervalSelect.value;

  try {
    // the three requests run at the same time
    const [forecast, weather, holidays] = await Promise.all([
      getJson("/forecast?date=" + date + "&target=" + target + "&interval=" + interval),
      getJson("/weather?date=" + date),
      getJson("/holidays?date=" + date),
    ]);
    renderKpis(forecast);
    renderForecastChart(forecast, holidays);
    renderWeather(weather);
    renderHolidays(holidays);
  } catch (error) {
    messageBox.textContent = "Could not load data: " + error.message;
  }
}

async function start() {
  try {
    const meta = await getJson("/meta");
    dateInput.min = meta.first_date;
    dateInput.max = meta.last_date;
    dateInput.value = meta.default_date;
  } catch (error) {
    messageBox.textContent = "Could not reach the API: " + error.message;
    return;
  }
  [dateInput, targetSelect, intervalSelect].forEach(el => el.addEventListener("change", loadDashboard));
  loadDashboard();
}

start();