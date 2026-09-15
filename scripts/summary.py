import json
import re
from pathlib import Path
import pandas as pd

# Load pipeline metrics and tables
metrics = pd.read_csv(snakemake.input.metrics, sep="\t").fillna("")
beta = pd.read_csv(snakemake.input.beta, sep="\t").fillna(0)

records = metrics.to_dict(orient="records")

def clean_tax_id(val):
    if pd.isna(val):
        return ""
    cleaned = re.sub(r"[,\s]", "", str(val).strip())
    if "." in cleaned:
        cleaned = cleaned.split(".")[0]
    return cleaned

bracken_data = {}
for path_str in snakemake.input.bracken:
    p = Path(path_str)
    sample_name = p.name[:-len(".bracken")]
    try:
        df_b = pd.read_csv(p, sep="\t").fillna("")
        for col in ("taxonomy_id", "tax_id", "taxID"):
            if col in df_b.columns:
                df_b[col] = df_b[col].apply(clean_tax_id)
        bracken_data[sample_name] = df_b.to_dict(orient="records")
    except Exception:
        bracken_data[sample_name] = []

centrifuge_data = {}
for path_str in snakemake.input.centrifuge:
    p = Path(path_str)
    sample_name = p.name[len("filtered_"):-len(".tsv")]
    try:
        df_c = pd.read_csv(p, sep="\t").fillna("")
        for col in ("taxID", "taxonomy_id", "tax_id"):
            if col in df_c.columns:
                df_c[col] = df_c[col].apply(clean_tax_id)
        centrifuge_data[sample_name] = df_c.to_dict(orient="records")
    except Exception:
        centrifuge_data[sample_name] = []

coverage_data = {}
for path_str in snakemake.input.coverage:
    p = Path(path_str)
    sample_name = p.name[:-len("_taxa_coverage.json")]
    try:
        with open(p, "r", encoding="utf-8") as f:
            coverage_data[sample_name] = json.load(f)
    except Exception:
        coverage_data[sample_name] = {}

comparison_data = {}
for path_str in snakemake.input.comparison:
    p = Path(path_str)
    sample_name = p.name[:-len("_taxa_comparison.tsv")]
    try:
        df_comp = pd.read_csv(p, sep="\t").fillna("")
        df_comp["Taxonomy ID"] = df_comp["Taxonomy ID"].apply(clean_tax_id)
        
        # Determine specific coverage status
        cov_sample = coverage_data.get(sample_name, {})
        def get_cov_status(tid):
            val = cov_sample.get(str(tid), "")
            if val == "REF_NOT_FOUND":
                return "No Reference"
            elif val == "NO_MAPPING_READS":
                return "Zero Mapped Reads"
            elif val and not val.startswith("ERROR_"):
                return "Available"
            return "Failed"

        df_comp["Coverage Map"] = df_comp["Taxonomy ID"].apply(get_cov_status)
        comparison_data[sample_name] = df_comp.to_dict(orient="records")
    except Exception:
        comparison_data[sample_name] = []

payload = {
    "metrics": records,
    "beta": beta.to_dict(orient="records"),
    "bracken": bracken_data,
    "centrifuge": centrifuge_data,
    "comparison": comparison_data,
    "coverage_plots": coverage_data
}

json_payload = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

html_document = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Results - Taxonomic Summary Dashboard</title>
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
  --purple: #7c3aed;
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
.cards { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; margin-bottom: 18px; }
.card, .panel { background: var(--card); border: 1px solid var(--border); border-radius: 12px; box-shadow: 0 2px 8px rgba(15, 35, 63, 0.04); }
.card { padding: 16px; min-height: 100px; }
.card-label { color: var(--muted); font-size: 12px; margin-bottom: 10px; }
.card-value { color: var(--navy); font-size: 22px; font-weight: 700; overflow-wrap: anywhere; }
.card-value.green { color: var(--green); }
.card-value.orange { color: var(--orange); }
.card-value.purple { color: var(--purple); }
.grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.panel { padding: 16px 18px 20px; min-height: 350px; }
.panel.wide { grid-column: 1 / -1; }
.panel h2 { color: var(--navy); font-size: 16px; margin: 0 0 12px 0; }
.plot { height: 285px; }
.table-wrap { overflow-x: auto; max-height: 480px; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { border-bottom: 1px solid var(--border); padding: 9px 8px; text-align: left; }
th { color: var(--muted); font-weight: 600; background: #f8fafc; position: sticky; top: 0; z-index: 2; }
.search-input { width: 100%; padding: 8px 12px; margin-bottom: 10px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; }

/* Status Badges */
.badge-yes { background: #dcfce7; color: #15803d; padding: 3px 10px; border-radius: 12px; font-weight: 600; font-size: 11px; display: inline-block; }
.badge-no { background: #f1f5f9; color: #94a3b8; padding: 3px 10px; border-radius: 12px; font-weight: 600; font-size: 11px; display: inline-block; }
.badge-gray { background: #f1f5f9; color: #64748b; padding: 3px 8px; border-radius: 12px; font-weight: 600; font-size: 11px; display: inline-block; }
.badge-amber { background: #fef3c7; color: #b45309; padding: 3px 8px; border-radius: 12px; font-weight: 600; font-size: 11px; display: inline-block; }
.badge-red { background: #fee2e2; color: #b91c1c; padding: 3px 8px; border-radius: 12px; font-weight: 600; font-size: 11px; display: inline-block; }

.btn-cov { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 600; cursor: pointer; }
.btn-cov:hover { background: #dbeafe; }

/* Modal overlay */
.modal-overlay { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.6); display: none; align-items: center; justify-content: center; z-index: 9999; }
.modal-content { background: white; border-radius: 10px; width: 90%; max-width: 900px; max-height: 85vh; display: flex; flex-direction: column; overflow: hidden; }
.modal-header { padding: 14px 20px; background: #f8fafc; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
.modal-header h3 { margin: 0; font-size: 16px; color: var(--navy); }
.modal-close { cursor: pointer; border: none; background: transparent; font-size: 20px; font-weight: bold; color: var(--muted); }
.modal-body { padding: 20px; overflow: auto; }
pre.ascii-cov { font-family: monospace; font-size: 12px; line-height: 1.35; white-space: pre; background: #0f172a; color: #38bdf8; padding: 16px; border-radius: 8px; margin: 0; }

.footer { color: var(--muted); text-align: center; font-size: 12px; margin-top: 22px; }
a.tax-link { color: var(--blue); text-decoration: none; font-weight: 600; }
a.tax-link:hover { text-decoration: underline; }

@media (max-width: 1200px) { .cards { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 768px) {
  .app { display: block; }
  .sidebar { position: static; width: 100%; }
  .main { margin-left: 0; width: 100%; padding: 20px 14px; }
  .grid, .cards { grid-template-columns: 1fr; }
  .panel.wide { grid-column: auto; }
}
</style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <div class="brand">Microbial Analysis<small>Kraken2, Bracken &amp; Centrifuge</small></div>
    <label for="sample-select">Select sample</label>
    <select id="sample-select"></select>
    <div class="note">Inspect QC metrics, multi-engine classifications, and coverage statistics.</div>
  </aside>

  <main class="main">
    <section class="header">
      <div>
        <h1>Summary Dashboard</h1>
        <p class="subtitle">Overall Summary of QC, Identification, Diversity and Reference Coverage</p>
      </div>
      <div class="badge" id="sample-badge">No sample selected</div>
    </section>

    <section class="cards">
      <div class="card"><div class="card-label">Raw reads</div><div class="card-value" id="raw-reads">—</div></div>
      <div class="card"><div class="card-label">Microbial reads</div><div class="card-value" id="microbial-reads">—</div></div>
      <div class="card"><div class="card-label">Kraken classified</div><div class="card-value green" id="classified-reads">—</div></div>
      <div class="card"><div class="card-label">Bracken estimated</div><div class="card-value orange" id="bracken-reads">—</div></div>
      <div class="card"><div class="card-label">Centrifuge estimated</div><div class="card-value purple" id="centrifuge-reads">—</div></div>
    </section>

    <section class="grid">
      <div class="panel"><h2>Alpha diversity</h2><div class="plot" id="alpha-plot"></div></div>
      <div class="panel"><h2>Beta diversity (Bray-Curtis Heatmap)</h2><div class="plot" id="beta-plot"></div></div>
      <div class="panel wide"><h2>Read counts by processing stage</h2><div class="plot" id="read-plot"></div></div>
      <div class="panel wide"><h2>FASTQ quality statistics</h2><div class="table-wrap" id="stats-table"></div></div>
      
      <div class="panel wide">
        <h2>Detected Taxa &amp; Abundance (Bracken)</h2>
        <input type="text" id="bracken-search" class="search-input" placeholder="Filter Bracken taxa..." />
        <div class="table-wrap" id="bracken-table-wrap"></div>
      </div>

      <div class="panel wide">
        <h2>Detected Taxa and number of reads (Centrifuge)</h2>
        <input type="text" id="centrifuge-search" class="search-input" placeholder="Filter Centrifuge taxa..." />
        <div class="table-wrap" id="centrifuge-table-wrap"></div>
      </div>

      <div class="panel wide">
        <h2>Summary &amp; Reference Coverage Details</h2>
        <input type="text" id="comparison-search" class="search-input" placeholder="Filter summary table..." />
        <div class="table-wrap" id="comparison-table-wrap"></div>
      </div>
    </section>
    <div class="footer">Smacked: Snakemake based Metagenome Assessment with Centrifuge and Kraken, Estimation and host Depletion</div>
  </main>
</div>

<div class="modal-overlay" id="coverage-modal">
  <div class="modal-content">
    <div class="modal-header">
      <h3 id="modal-taxid-title">Taxonomy ID Coverage</h3>
      <button class="modal-close" onclick="closeModal()">&times;</button>
    </div>
    <div class="modal-body">
      <pre class="ascii-cov" id="modal-cov-content"></pre>
    </div>
  </div>
</div>

<script>
const DATA = __PAYLOAD__;
const select = document.getElementById('sample-select');
const plotConfig = {responsive: true, displaylogo: false};
const layoutBase = {font: {family: 'Arial, sans-serif', color: '#1e293b'}, paper_bgcolor: 'white', plot_bgcolor: 'white', margin: {t: 20, r: 20, b: 55, l: 60}, legend: {orientation: 'h', y: -0.2}};

let currentSample = "";
let currentBracken = [];
let currentCentrifuge = [];
let currentComparison = [];

function openModal(taxId) {
  const sampleCoverage = DATA.coverage_plots[currentSample] || {};
  const plotStr = sampleCoverage[taxId] || "No coverage map generated for this taxonomy ID.";
  document.getElementById('modal-taxid-title').textContent = `Coverage Histogram (samtools coverage -m) — TaxID: ${taxId}`;
  document.getElementById('modal-cov-content').textContent = plotStr;
  document.getElementById('coverage-modal').style.display = 'flex';
}

function closeModal() {
  document.getElementById('coverage-modal').style.display = 'none';
}

function number(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatNumber(value) {
  const parsed = number(value);
  return parsed === null ? '—' : parsed.toLocaleString(undefined, {maximumFractionDigits: 4});
}

function formatCell(key, val, row) {
  const kLower = String(key).toLowerCase().replace(/[\s_\-]/g, '');
  
  if (kLower === 'taxonomyid' || kLower === 'taxid') {
    return String(val).replace(/,/g, '');
  }
  if (kLower === 'coveragemap') {
    const tid = String(row['Taxonomy ID'] || row['taxID'] || '').replace(/,/g, '');
    if (val === 'Available') {
      return `<button class="btn-cov" onclick="openModal('${tid}')">View -m Plot</button>`;
    }
    if (val === 'No Reference') {
      return '<span class="badge-gray">No RefSeq Genome</span>';
    }
    if (val === 'Zero Mapped Reads') {
      return '<span class="badge-amber">0 Mapped Reads</span>';
    }
    return '<span class="badge-red">Failed</span>';
  }
  if (String(val).startsWith('http://') || String(val).startsWith('https://')) {
    return `<a href="${val}" target="_blank" rel="noopener noreferrer" class="tax-link">NCBI Browser</a>`;
  }
  if (val === 'Yes') return '<span class="badge-yes">Yes</span>';
  if (val === 'No') return '<span class="badge-no">No</span>';
  if (typeof val === 'number') return formatNumber(val);
  return val;
}

function getSample(sample) {
  return DATA.metrics.find(row => String(row.sample) === String(sample));
}

function renderTable(containerId, rows, emptyMsg) {
  const container = document.getElementById(containerId);
  if (!rows || rows.length === 0) {
    container.innerHTML = `<p style="color:var(--muted); padding: 8px;">${emptyMsg}</p>`;
    return;
  }
  const headers = Object.keys(rows[0]);
  let html = '<table><thead><tr>' + headers.map(h => `<th>${h}</th>`).join('') + '</tr></thead><tbody>';
  rows.forEach(r => {
    html += '<tr>' + headers.map(h => `<td>${formatCell(h, r[h], r)}</td>`).join('') + '</tr>';
  });
  html += '</tbody></table>';
  container.innerHTML = html;
}

function updateTable(row) {
  const rows = [
    ['Raw', 'Reads', row.raw_num_seqs], ['Raw', 'Total bases', row.raw_sum_len], ['Raw', 'Average length', row.raw_avg_len],
    ['Trimmed', 'Reads', row.trimmed_num_seqs], ['Trimmed', 'Total bases', row.trimmed_sum_len], ['Trimmed', 'Average length', row.trimmed_avg_len],
    ['Microbial', 'Reads', row.microbial_num_seqs], ['Microbial', 'Total bases', row.microbial_sum_len], ['Microbial', 'Average length', row.microbial_avg_len],
  ];
  document.getElementById('stats-table').innerHTML = '<table><thead><tr><th>Stage</th><th>Metric</th><th>Value</th></tr></thead><tbody>' + rows.map(r => `<tr><td>${r[0]}</td><td>${r[1]}</td><td>${formatNumber(r[2])}</td></tr>`).join('') + '</tbody></table>';
}

function renderBetaHeatmap() {
  if (!DATA.beta || DATA.beta.length === 0) return;
  const sampleList = Array.from(new Set(DATA.beta.flatMap(d => [d.sample_a, d.sample_b]))).filter(Boolean).sort();
  if (sampleList.length === 0) return;

  const distMap = {};
  DATA.beta.forEach(d => {
    distMap[`${d.sample_a}___${d.sample_b}`] = number(d.bray_curtis) ?? 0;
    distMap[`${d.sample_b}___${d.sample_a}`] = number(d.bray_curtis) ?? 0;
  });

  const z = sampleList.map(s1 => sampleList.map(s2 => s1 === s2 ? 0 : (distMap[`${s1}___${s2}`] ?? 0)));

  const trace = {
    z: z,
    x: sampleList,
    y: sampleList,
    type: 'heatmap',
    colorscale: [
      [0, '#f0f9ff'],
      [0.25, '#bae6fd'],
      [0.5, '#38bdf8'],
      [0.75, '#2563eb'],
      [1, '#1e3a8a']
    ],
    zmin: 0,
    zmax: 1,
    colorbar: { title: 'Bray-Curtis', titleside: 'right', len: 0.9, thickness: 12 },
    hoverongaps: false
  };

  Plotly.react('beta-plot', [trace], {
    ...layoutBase,
    margin: { t: 20, r: 20, b: 65, l: 65 },
    xaxis: { tickangle: -35, automargin: true },
    yaxis: { automargin: true }
  }, plotConfig);
}

function updateDashboard(sample) {
  const row = getSample(sample);
  if (!row) return;
  currentSample = row.sample;

  document.getElementById('sample-badge').textContent = `Sample: ${row.sample}`;
  document.getElementById('raw-reads').textContent = formatNumber(row.raw_num_seqs);
  document.getElementById('microbial-reads').textContent = formatNumber(row.microbial_num_seqs);
  document.getElementById('classified-reads').textContent = formatNumber(row.kraken_classified_reads);
  document.getElementById('bracken-reads').textContent = formatNumber(row.bracken_estimated_reads);
  document.getElementById('centrifuge-reads').textContent = formatNumber(row.centrifuge_estimated_reads);

  const alphaKeys = Object.keys(row).filter(key => key.startsWith('alpha_'));
  Plotly.react('alpha-plot', [{x: alphaKeys.map(key => key.replace('alpha_', '')), y: alphaKeys.map(key => number(row[key])), type: 'bar', marker: {color: '#2563eb'}}], {...layoutBase, yaxis: {title: 'Index value'}, xaxis: {title: 'Metric', tickangle: -30}}, plotConfig);

  Plotly.react('read-plot', [{x: ['Raw', 'Trimmed', 'Microbial'], y: [number(row.raw_num_seqs), number(row.trimmed_num_seqs), number(row.microbial_num_seqs)], type: 'bar', marker: {color: ['#64748b', '#2563eb', '#059669']}}], {...layoutBase, yaxis: {title: 'Number of reads'}, showlegend: false}, plotConfig);
  updateTable(row);

  currentBracken = DATA.bracken[row.sample] || [];
  currentCentrifuge = DATA.centrifuge[row.sample] || [];
  currentComparison = DATA.comparison[row.sample] || [];

  document.getElementById('bracken-search').value = '';
  document.getElementById('centrifuge-search').value = '';
  document.getElementById('comparison-search').value = '';

  renderTable('bracken-table-wrap', currentBracken, 'No Bracken data found for this sample.');
  renderTable('centrifuge-table-wrap', currentCentrifuge, 'No Centrifuge data found for this sample.');
  renderTable('comparison-table-wrap', currentComparison, 'No summary data found for this sample.');
}

document.getElementById('bracken-search').addEventListener('input', e => {
  const query = e.target.value.toLowerCase();
  renderTable('bracken-table-wrap', currentBracken.filter(r => Object.values(r).some(v => String(v).toLowerCase().includes(query))), 'No matching Bracken taxa.');
});

document.getElementById('centrifuge-search').addEventListener('input', e => {
  const query = e.target.value.toLowerCase();
  renderTable('centrifuge-table-wrap', currentCentrifuge.filter(r => Object.values(r).some(v => String(v).toLowerCase().includes(query))), 'No matching Centrifuge taxa.');
});

document.getElementById('comparison-search').addEventListener('input', e => {
  const query = e.target.value.toLowerCase();
  renderTable('comparison-table-wrap', currentComparison.filter(r => Object.values(r).some(v => String(v).toLowerCase().includes(query))), 'No matching summary taxa.');
});

DATA.metrics.forEach(row => {
  const option = document.createElement('option');
  option.value = row.sample;
  option.textContent = row.sample;
  select.appendChild(option);
});
select.addEventListener('change', event => updateDashboard(event.target.value));

renderBetaHeatmap();
if (DATA.metrics.length > 0) updateDashboard(DATA.metrics[0].sample);
</script>
</body>
</html>'''

html_document = html_document.replace("__PAYLOAD__", json_payload)
Path(snakemake.output.html).parent.mkdir(parents=True, exist_ok=True)
Path(snakemake.output.html).write_text(html_document, encoding="utf-8")