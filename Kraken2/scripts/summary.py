import json
from pathlib import Path

import pandas as pd


metrics = pd.read_csv(snakemake.input.metrics, sep="\t").fillna("")
beta = pd.read_csv(snakemake.input.beta, sep="\t").fillna(0)

records = metrics.to_dict(orient="records")

krona_reports = {}
for record in records:
    sample = str(record["sample"])
    krona_path = record.get("krona_html", "")
    try:
        krona_reports[sample] = Path(krona_path).read_text(
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, TypeError):
        krona_reports[sample] = (
            "<html><body><p>Krona report unavailable.</p></body></html>"
        )

payload = {
    "metrics": records,
    "beta": beta.to_dict(orient="records"),
    "krona": krona_reports,
}

json_payload = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

html_document = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kraken and Bracken Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
:root {
  --navy: #10233f;
  --blue: #2563eb;
  --blue-light: #e8f0ff;
  --background: #f4f7fb;
  --card: #ffffff;
  --border: #e3e9f2;
  --text: #1e293b;
  --muted: #64748b;
  --green: #059669;
  --orange: #ea580c;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--background); color: var(--text); font-family: Inter, Arial, sans-serif; }
.app { display: flex; min-height: 100vh; }
.sidebar { width: 260px; background: var(--navy); color: white; padding: 28px 20px; position: fixed; inset: 0 auto 0 0; }
.brand { font-size: 21px; font-weight: 700; line-height: 1.25; margin-bottom: 36px; }
.brand small { display: block; color: #a9bad3; font-size: 12px; font-weight: 400; margin-top: 8px; }
.sidebar label { color: #b9c8dc; font-size: 12px; display: block; margin-bottom: 8px; }
.sidebar select { width: 100%; border: 0; border-radius: 7px; padding: 11px 9px; font-size: 14px; color: var(--text); }
.sidebar .note { color: #a9bad3; font-size: 12px; line-height: 1.5; margin-top: 24px; }
.main { margin-left: 260px; width: calc(100% - 260px); padding: 30px 34px 45px; }
.header { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; margin-bottom: 24px; }
h1 { margin: 0; font-size: 28px; color: var(--navy); }
.subtitle { margin: 7px 0 0; color: var(--muted); font-size: 14px; }
.badge { background: var(--blue-light); color: var(--blue); padding: 8px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; }
.cards { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin-bottom: 18px; }
.card, .panel { background: var(--card); border: 1px solid var(--border); border-radius: 12px; box-shadow: 0 2px 8px rgba(15, 35, 63, 0.04); }
.card { padding: 18px; min-height: 105px; }
.card-label { color: var(--muted); font-size: 12px; margin-bottom: 12px; }
.card-value { color: var(--navy); font-size: 25px; font-weight: 700; overflow-wrap: anywhere; }
.card-value.green { color: var(--green); }
.card-value.orange { color: var(--orange); }
.grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.panel { padding: 8px 12px 12px; min-height: 350px; }
.panel.wide { grid-column: 1 / -1; }
.panel h2 { color: var(--navy); font-size: 16px; margin: 10px 8px 0; }
.plot { height: 285px; }
.table-wrap { overflow-x: auto; padding: 10px 8px; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { border-bottom: 1px solid var(--border); padding: 10px 8px; text-align: left; }
th { color: var(--muted); font-weight: 600; background: #f8fafc; }
#krona-frame { width: 100%; height: 650px; border: 0; border-radius: 800px; background: white; }
.footer { color: var(--muted); text-align: center; font-size: 12px; margin-top: 22px; }
@media (max-width: 1000px) { .cards { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 720px) {
  .app { display: block; }
  .sidebar { position: static; width: 100%; }
  .main { margin-left: 0; width: 100%; padding: 22px 15px; }
  .grid, .cards { grid-template-columns: 1fr; }
  .panel.wide { grid-column: auto; }
  .header { display: block; }
  .badge { display: inline-block; margin-top: 14px; }
}
</style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <div class="brand">Microbial Analysis<small>Kraken2 / Bracken dashboard</small></div>
    <label for="sample-select">Select sample</label>
    <select id="sample-select"></select>
    <div class="note">Choose a sample to update all plots, read statistics, and the embedded Krona report.</div>
  </aside>

  <main class="main">
    <section class="header">
      <div>
        <h1>Interactive Taxonomic Summary</h1>
        <p class="subtitle">Quality control, taxonomic classification, and diversity overview</p>
      </div>
      <div class="badge" id="sample-badge">No sample selected</div>
    </section>

    <section class="cards">
      <div class="card"><div class="card-label">Raw reads</div><div class="card-value" id="raw-reads">—</div></div>
      <div class="card"><div class="card-label">Microbial reads</div><div class="card-value" id="microbial-reads">—</div></div>
      <div class="card"><div class="card-label">Kraken classified</div><div class="card-value green" id="classified-reads">—</div></div>
      <div class="card"><div class="card-label">Bracken estimated</div><div class="card-value orange" id="bracken-reads">—</div></div>
    </section>

    <section class="grid">
      <div class="panel"><h2>Alpha diversity</h2><div class="plot" id="alpha-plot"></div></div>
      <div class="panel"><h2>Beta diversity</h2><div class="plot" id="beta-plot"></div></div>
      <div class="panel wide"><h2>Read counts by processing stage</h2><div class="plot" id="read-plot"></div></div>
      <div class="panel wide"><h2>FASTQ quality statistics</h2><div class="table-wrap" id="stats-table"></div></div>
      <div class="panel wide"><h2>Krona taxonomy view</h2><iframe id="krona-frame" title="Krona taxonomy report"></iframe></div>
    </section>
    <div class="footer">Generated by Snakemake, Kraken2, Bracken, KrakenTools, Seqkit, and Plotly</div>
  </main>
</div>

<script>
const DATA = __PAYLOAD__;
const select = document.getElementById('sample-select');
const plotConfig = {responsive: true, displaylogo: false};
const layoutBase = {font: {family: 'Arial, sans-serif', color: '#1e293b'}, paper_bgcolor: 'white', plot_bgcolor: 'white', margin: {t: 20, r: 20, b: 55, l: 60}, legend: {orientation: 'h', y: -0.2}};

function number(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatNumber(value) {
  const parsed = number(value);
  return parsed === null ? '—' : parsed.toLocaleString(undefined, {maximumFractionDigits: 2});
}

function getSample(sample) {
  return DATA.metrics.find(row => String(row.sample) === String(sample));
}

function updateTable(row) {
  const rows = [
    ['Raw', 'Reads', row.raw_num_seqs], ['Raw', 'Total bases', row.raw_sum_len], ['Raw', 'Average length', row.raw_avg_len],
    ['Trimmed', 'Reads', row.trimmed_num_seqs], ['Trimmed', 'Total bases', row.trimmed_sum_len], ['Trimmed', 'Average length', row.trimmed_avg_len],
    ['Microbial', 'Reads', row.microbial_num_seqs], ['Microbial', 'Total bases', row.microbial_sum_len], ['Microbial', 'Average length', row.microbial_avg_len],
  ];
  document.getElementById('stats-table').innerHTML = '<table><thead><tr><th>Stage</th><th>Metric</th><th>Value</th></tr></thead><tbody>' + rows.map(r => `<tr><td>${r[0]}</td><td>${r[1]}</td><td>${formatNumber(r[2])}</td></tr>`).join('') + '</tbody></table>';
}

function updateDashboard(sample) {
  const row = getSample(sample);
  if (!row) return;
  document.getElementById('sample-badge').textContent = `Sample: ${row.sample}`;
  document.getElementById('raw-reads').textContent = formatNumber(row.raw_num_seqs);
  document.getElementById('microbial-reads').textContent = formatNumber(row.microbial_num_seqs);
  document.getElementById('classified-reads').textContent = formatNumber(row.kraken_classified_reads);
  document.getElementById('bracken-reads').textContent = formatNumber(row.bracken_estimated_reads);

  const alphaKeys = Object.keys(row).filter(key => key.startsWith('alpha_'));
  Plotly.react('alpha-plot', [{x: alphaKeys.map(key => key.replace('alpha_', 'Shannon')), y: alphaKeys.map(key => number(row[key])), type: 'bar', marker: {color: '#2563eb'}}], {...layoutBase, yaxis: {title: 'Index value'}, xaxis: {title: 'Index'}} , plotConfig);

  const distances = DATA.beta.filter(item => item.sample_a === row.sample || item.sample_b === row.sample).map(item => ({label: item.sample_a === row.sample ? item.sample_b : item.sample_a, value: number(item.bray_curtis)}));
  Plotly.react('beta-plot', [{x: distances.map(item => item.label), y: distances.map(item => item.value), type: 'bar', marker: {color: '#ea580c'}}], {...layoutBase, yaxis: {title: 'Bray-Curtis', range: [0, 1]}, xaxis: {tickangle: -35}}, plotConfig);

  Plotly.react('read-plot', [{x: ['Raw', 'Trimmed', 'Microbial'], y: [number(row.raw_num_seqs), number(row.trimmed_num_seqs), number(row.microbial_num_seqs)], type: 'bar', marker: {color: ['#64748b', '#2563eb', '#059669']}}], {...layoutBase, yaxis: {title: 'Number of reads'}, showlegend: false}, plotConfig);
  updateTable(row);
  document.getElementById('krona-frame').srcdoc = DATA.krona[row.sample] || '<html><body><p>Krona report unavailable.</p></body></html>';
}

DATA.metrics.forEach(row => {
  const option = document.createElement('option');
  option.value = row.sample;
  option.textContent = row.sample;
  select.appendChild(option);
});
select.addEventListener('change', event => updateDashboard(event.target.value));
if (DATA.metrics.length > 0) updateDashboard(DATA.metrics[0].sample);
</script>
</body>
</html>'''

html_document = html_document.replace("__PAYLOAD__", json_payload)
Path(snakemake.output.html).parent.mkdir(parents=True, exist_ok=True)
Path(snakemake.output.html).write_text(html_document, encoding="utf-8")
