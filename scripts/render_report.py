"""Create a self-contained, printable comparison report from measured results."""

import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render():
    source = ROOT / "docs/evaluation-pdf.json"
    if not source.exists():
        source = ROOT / "docs/evaluation.json"
    r = json.loads(source.read_text())
    rows = []
    for name, v in r["results"].items():
        cells = [
            name,
            str(v["chunks"]),
            f"{v['recall_at_6']:.1%}",
            f"{v['precision_at_6']:.1%}",
            f"{v['mrr_at_6']:.3f}",
            f"{v['median_ms']:.1f} ms",
        ]
        rows.append(
            "<tr>" + "".join("<td>" + escape(x) + "</td>" for x in cells) + "</tr>"
        )
    failures = []
    for name, v in r["results"].items():
        items = [q for q in v["questions"] if q["recall"] < 1]
        failures.append(
            "<h3>"
            + escape(name)
            + "</h3><ul>"
            + "".join(
                "<li>"
                + escape(q["case_id"] + " — " + q["question"])
                + f" · evidence recall {q['recall']:.2f}</li>"
                for q in items
            )
            + "</ul>"
        )
    style = "body{font:15px/1.7 system-ui,sans-serif;background:#f6f6ee;color:#243b34;margin:0;padding:48px}main{max-width:1100px;margin:auto}h1{font:44px Georgia,serif}h2{font:28px Georgia,serif;margin-top:36px}.eyebrow{font-size:11px;letter-spacing:2px;color:#6b8868}table{border-collapse:collapse;width:100%;background:white;font-size:13px}th,td{text-align:left;padding:12px;border-bottom:1px solid #e0e5d7}th{background:#e7eedf}.note{background:#e9eedf;border-left:3px solid #6d8c61;padding:18px}code{overflow-wrap:anywhere}li{margin-bottom:7px}@media print{body{padding:10px;background:white}tr{break-inside:avoid}h2,h3{break-after:avoid}}"
    text = (
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Customer Case Intelligence — Return &amp; Refund Intelligence · Comparison report</title><style>'
        + style
        + '</style><main><div class="eyebrow">CUSTOMER CASE INTELLIGENCE · RETURN &amp; REFUND INTELLIGENCE</div><p>One case. Every connection.</p><h1>Chunking & reranking,<br>measured on the same questions.</h1><p>87 fictional source records in PDFs · Four public-reference notes · 32 unchanged benchmark queries</p><div class="note">'
        + escape(r["protocol"])
        + "</div><p>"
        + escape(r.get("reranker_input", ""))
        + "</p><h2>Measured results</h2><table><thead><tr><th>Configuration</th><th>Chunks</th><th>Evidence recall@6</th><th>Precision@6</th><th>MRR@6</th><th>Median latency</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table><p>"
        + escape(r.get("conclusion", ""))
        + "</p><h2>Paired cross-encoder impact</h2>"
    )
    for prefix in ("fixed", "semantic"):
        d = r[prefix + "_reranking_delta"]
        text += f"<p><strong>{prefix}</strong>: recall {d['recall_at_6'] * 100:+.2f} percentage points; precision {d['precision_at_6'] * 100:+.2f} points; MRR {d['mrr_at_6']:+.3f}; latency {d['median_ms']:+.1f} ms.</p>"
    table_path = ROOT / "docs/table-evaluation.json"
    if table_path.exists():
        tables = json.loads(table_path.read_text())
        text += "<h2>Supplemental financial table probe</h2><p>Eight source-specific questions require the tax allocation and control total from the designated order confirmation. This probe informed development and is not held out.</p><table><tr><th>Configuration</th><th>Evidence recall@6</th></tr>"
        for name, value in tables["results"].items():
            text += (
                "<tr><td>"
                + escape(name)
                + "</td><td>"
                + f"{value['table_evidence_recall_at_6']:.1%}"
                + "</td></tr>"
            )
        text += "</table><p>The initial table-aware cross-encoder confused identical tables from different sources; source provenance was added to its input. Original results are retained in the iterations folder.</p>"
    text += (
        "<h2>Incomplete-evidence questions</h2>"
        + "".join(failures)
        + "<h2>Scope and limitations</h2><ul>"
        + "".join("<li>" + escape(x) + "</li>" for x in r["limitations"])
        + "</ul><p>"
        + escape(r["faithfulness"])
        + "</p><p>Reranker: <code>"
        + escape(r["reranker"])
        + "</code></p><p>Corpus SHA-256: <code>"
        + r["corpus_sha256"]
        + "</code></p></main></html>"
    )
    (ROOT / "docs/comparison-report.html").write_text(text)


if __name__ == "__main__":
    render()
