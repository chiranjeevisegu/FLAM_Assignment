from flask import Flask, render_template_string, redirect, url_for, request
from job_store import JobStore
from dlq import DLQ

app = Flask(__name__)
store = JobStore()
dlq = DLQ()

TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title> FLAM Monitoring Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<meta http-equiv="refresh" content="10">
<style>
body {
  font-family: 'Segoe UI', sans-serif; margin: 0; background: #eef2f7;
}
header {
  background: linear-gradient(90deg,#0f2027,#203a43,#2c5364);
  color: white; padding: 20px; text-align: center;
}
.container { padding: 30px; }
.cards { display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 30px; }
.card {
  flex: 1; min-width: 180px; color: white; text-align: center;
  border-radius: 10px; padding: 15px;
  box-shadow: 0 3px 8px rgba(0,0,0,0.2);
  animation: pop 0.6s ease;
}
@keyframes pop { 0%{transform:scale(0.9);} 100%{transform:scale(1);} }
.total { background: linear-gradient(45deg,#3498db,#2980b9); }
.completed { background: linear-gradient(45deg,#27ae60,#2ecc71); }
.dead { background: linear-gradient(45deg,#e74c3c,#c0392b); }
.duration { background: linear-gradient(45deg,#8e44ad,#9b59b6); }
.rate { background: linear-gradient(45deg,#f39c12,#e67e22); }

table {
  width: 100%; border-collapse: collapse; background: white; margin-bottom: 40px;
}
th, td {
  padding: 10px; border: 1px solid #ccc; text-align: left;
}
th {
  background: #2c3e50; color: white;
}
button {
  background: #3498db; color: white; border: none; padding: 6px 10px;
  border-radius: 5px; cursor: pointer; transition: 0.2s;
}
button:hover { background: #2c3e50; }
.chart-grid { display: flex; gap: 20px; flex-wrap: wrap; justify-content: space-around; }
.chart-box { width: 320px; height: 320px; background: white; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); padding: 10px; }
</style>
</head>
<body>
<header><h1> FLAM Monitoring Dashboard</h1><p>Auto-refreshes every 10 seconds</p></header>
<div class="container">

<div class="cards">
  <div class="card total"><h2>{{summary.total}}</h2><p>Total Jobs</p></div>
  <div class="card completed"><h2>{{summary.completed}}</h2><p>Completed</p></div>
  <div class="card dead"><h2>{{summary.dead}}</h2><p>Dead</p></div>
  <div class="card duration"><h2>{{summary.avg_duration}}</h2><p>Avg Duration (s)</p></div>
  <div class="card rate"><h2>{{summary.success_rate}}%</h2><p>Success Rate</p></div>
</div>

<div class="chart-grid">
  <div class="chart-box"><canvas id="pieChart"></canvas></div>
  <div class="chart-box"><canvas id="barChart"></canvas></div>
</div>

<h2>🧾 Recent Jobs</h2>
<table>
<tr><th>ID</th><th>COMMAND</th><th>STATE</th><th>PRIORITY</th><th>ATTEMPTS</th><th>DURATION (s)</th></tr>
{% for j in jobs %}
<tr><td>{{j[0]}}</td><td>{{j[1]}}</td><td>{{j[2]}}</td><td>{{j[8]}}</td><td>{{j[3]}}</td><td>{{"%.3f"|format(j[9] or 0)}}</td></tr>
{% endfor %}
</table>

<h2>☠️ Dead Letter Queue (DLQ)</h2>
<table>
<tr><th>ID</th><th>COMMAND</th><th>ERROR</th><th>MOVED AT</th><th>ACTION</th></tr>
{% for d in dlq_rows %}
<tr>
<td>{{d[0]}}</td><td>{{d[1]}}</td><td>{{d[6]}}</td><td>{{d[5]}}</td>
<td><form method="POST" action="{{url_for('retry_dlq',job_id=d[0])}}">
<button type="submit">♻ Retry</button></form></td>
</tr>
{% endfor %}
</table>

</div>

<script>
const pie = document.getElementById('pieChart');
new Chart(pie,{
  type:'pie',
  data:{labels:['Completed','Dead'],
  datasets:[{data:[{{summary.completed}},{{summary.dead}}],
  backgroundColor:['#27ae60','#e74c3c']}]}});
const bar = document.getElementById('barChart');
new Chart(bar,{
  type:'bar',
  data:{labels:['Total','Completed','Dead'],
  datasets:[{label:'Jobs Count',data:[{{summary.total}},{{summary.completed}},{{summary.dead}}],
  backgroundColor:['#3498db','#2ecc71','#e74c3c']}]},
  options:{scales:{y:{beginAtZero:true}}}});
</script>
</body>
</html>
"""

@app.route("/")
def index():
    m = store.metrics()
    summary = {
        "total": m["total"], "completed": m["completed"], "dead": m["dead"],
        "avg_duration": round(m["avg_duration"], 3), "success_rate": round(m["success_rate"], 2)
    }
    cur = store.conn.cursor()
    cur.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 15")
    jobs = cur.fetchall()
    dlq_rows = dlq.list_dlq()
    return render_template_string(TEMPLATE, summary=summary, jobs=jobs, dlq_rows=dlq_rows)

@app.route("/retry/<job_id>", methods=["POST"])
def retry_dlq(job_id):
    try:
        dlq.retry_job(job_id)
        print(f"♻ Retried DLQ job {job_id}")
        return redirect(url_for('index'))
    except Exception as e:
        print("❌ Error retrying job:", e)
        return f"Error retrying job: {e}", 500

if __name__ == "__main__":
    print("🚀 FLAM Dashboard → http://localhost:5000")
    app.run(port=5000, debug=False)
