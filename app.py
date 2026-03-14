from flask import Flask, render_template, request, send_file, jsonify
import pandas as pd
import os
from fpdf import FPDF
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import tempfile

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Store last results for PDF download
last_compare_data = {}
last_single_data = {}


def add_table_to_pdf(pdf, df, max_col_width=None):
    """Add a styled table from a dataframe to the PDF."""
    cols = list(df.columns)
    col_count = len(cols)
    page_width = pdf.w - 20
    col_width = min(page_width / col_count, max_col_width) if max_col_width else page_width / col_count

    # Header
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_fill_color(102, 126, 234)
    pdf.set_text_color(255, 255, 255)
    for col in cols:
        pdf.cell(col_width, 7, str(col), border=1, align='C', fill=True)
    pdf.ln()

    # Rows
    pdf.set_font('Helvetica', '', 7)
    pdf.set_text_color(30, 30, 30)
    for i, (_, row) in enumerate(df.iterrows()):
        if pdf.get_y() > pdf.h - 20:
            pdf.add_page()
            # Re-draw header
            pdf.set_font('Helvetica', 'B', 8)
            pdf.set_fill_color(102, 126, 234)
            pdf.set_text_color(255, 255, 255)
            for col in cols:
                pdf.cell(col_width, 7, str(col), border=1, align='C', fill=True)
            pdf.ln()
            pdf.set_font('Helvetica', '', 7)
            pdf.set_text_color(30, 30, 30)
        if i % 2 == 0:
            pdf.set_fill_color(245, 247, 250)
        else:
            pdf.set_fill_color(255, 255, 255)
        for col in cols:
            val = str(row[col])
            pdf.cell(col_width, 6, val, border=1, align='C', fill=True)
        pdf.ln()


def add_section_title(pdf, title, emoji=""):
    """Add a styled section title."""
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(102, 126, 234)
    pdf.cell(0, 10, f"{emoji}  {title}", ln=True)
    pdf.ln(2)


def add_stat_box(pdf, label, value, x, y, w=60, h=22):
    """Draw a stat box at a specific position."""
    pdf.set_xy(x, y)
    pdf.set_fill_color(245, 247, 250)
    pdf.set_draw_color(200, 200, 220)
    pdf.rect(x, y, w, h, 'DF')
    pdf.set_xy(x, y + 2)
    pdf.set_font('Helvetica', '', 7)
    pdf.set_text_color(120, 120, 140)
    pdf.cell(w, 5, label, align='C')
    pdf.set_xy(x, y + 8)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(30, 30, 60)
    pdf.cell(w, 10, str(value), align='C')


def create_pie_chart(labels, sizes, colors, title, filepath):
    """Create a pie chart and save as image."""
    fig, ax = plt.subplots(figsize=(4, 3))
    wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors,
                                       autopct='%1.1f%%', startangle=90,
                                       textprops={'fontsize': 9})
    for t in autotexts:
        t.set_fontsize(8)
        t.set_fontweight('bold')
    ax.set_title(title, fontsize=11, fontweight='bold', color='#333')
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()


def create_bar_chart(labels, values1, values2, label1, label2, title, filepath):
    """Create a grouped bar chart and save as image."""
    fig, ax = plt.subplots(figsize=(4, 3))
    x = range(len(labels))
    width = 0.35
    bars1 = ax.bar([i - width/2 for i in x], values1, width, label=label1,
                   color='#667eea')
    bars2 = ax.bar([i + width/2 for i in x], values2, width, label=label2,
                   color='#48bb78')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_title(title, fontsize=11, fontweight='bold', color='#333')
    ax.legend(fontsize=8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()


def create_single_bar_chart(labels, values, colors, title, filepath):
    """Create a simple bar chart."""
    fig, ax = plt.subplots(figsize=(4, 3))
    bars = ax.bar(labels, values, color=colors, width=0.5)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.5,
                str(val), ha='center', va='bottom', fontsize=9, fontweight='bold')
    ax.set_title(title, fontsize=11, fontweight='bold', color='#333')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()


def generate_single_pdf(by_marks, by_sgpa, failed_df, passed_count, failed_count, pass_pct, fail_pct):
    """Generate comprehensive PDF for single semester analysis."""
    pdf = FPDF(orientation='L', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)

    # === PAGE 1: Title + Stats + Charts ===
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 22)
    pdf.set_text_color(102, 126, 234)
    pdf.cell(0, 14, 'JNTU Topper Analyzer - Result Analysis', ln=True, align='C')
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, 'Comprehensive analysis report with rankings, charts & statistics', ln=True, align='C')
    pdf.ln(8)

    # Stats boxes
    total = passed_count + failed_count
    start_x = 30
    y = pdf.get_y()
    add_stat_box(pdf, 'TOTAL STUDENTS', total, start_x, y, 55)
    add_stat_box(pdf, 'PASSED', f"{passed_count} ({pass_pct}%)", start_x + 62, y, 55)
    add_stat_box(pdf, 'FAILED', f"{failed_count} ({fail_pct}%)", start_x + 124, y, 55)
    avg_sgpa = round(by_sgpa["SGPA"].mean(), 2) if len(by_sgpa) > 0 else 0
    add_stat_box(pdf, 'AVG SGPA', avg_sgpa, start_x + 186, y, 55)
    pdf.set_y(y + 30)

    # Charts
    with tempfile.TemporaryDirectory() as tmpdir:
        # Pie chart
        pie_path = os.path.join(tmpdir, 'pie.png')
        if passed_count > 0 or failed_count > 0:
            create_pie_chart(['Passed', 'Failed'], [passed_count, failed_count],
                           ['#48bb78', '#fc8181'], 'Pass/Fail Distribution', pie_path)
            pdf.image(pie_path, x=30, y=pdf.get_y(), w=120)

        # Bar chart - Top 5 SGPA
        bar_path = os.path.join(tmpdir, 'toppers_bar.png')
        top5 = by_sgpa.head(5)
        if len(top5) > 0:
            create_single_bar_chart(
                top5['HTNO'].tolist(), top5['SGPA'].tolist(),
                ['#667eea', '#764ba2', '#48bb78', '#ecc94b', '#fc8181'],
                'Top 5 Students by SGPA', bar_path
            )
            pdf.image(bar_path, x=160, y=pdf.get_y(), w=120)

    # === PAGE 2: Top 3 Toppers ===
    pdf.add_page()
    add_section_title(pdf, 'Top 3 Toppers by Total Marks')
    top3_marks = by_marks.head(3).copy()
    top3_marks['S.No'] = range(1, len(top3_marks)+1)
    add_table_to_pdf(pdf, top3_marks)
    pdf.ln(8)

    add_section_title(pdf, 'Top 3 Toppers by SGPA')
    top3_sgpa = by_sgpa.head(3).copy()
    top3_sgpa['S.No'] = range(1, len(top3_sgpa)+1)
    add_table_to_pdf(pdf, top3_sgpa)

    # === PAGE 3+: Full Rankings by Marks ===
    pdf.add_page()
    add_section_title(pdf, 'Complete Ranking by Total Marks')
    add_table_to_pdf(pdf, by_marks)

    # === Next: Full Rankings by SGPA ===
    pdf.add_page()
    add_section_title(pdf, 'Complete Ranking by SGPA')
    add_table_to_pdf(pdf, by_sgpa)

    # === Next: Failed Students ===
    if len(failed_df) > 0:
        pdf.add_page()
        add_section_title(pdf, 'Failed Students')
        add_table_to_pdf(pdf, failed_df)

    path = os.path.join(UPLOAD_FOLDER, 'output.pdf')
    pdf.output(path)
    return path


def generate_compare_pdf(result_data):
    """Generate comprehensive PDF for compare semesters."""
    r = result_data['result']
    common = result_data['common']

    pdf = FPDF(orientation='L', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)

    # === PAGE 1: Title + Overview ===
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 22)
    pdf.set_text_color(102, 126, 234)
    pdf.cell(0, 14, 'JNTU Topper Analyzer - Semester Comparison', ln=True, align='C')
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, 'Side-by-side comparison with charts and student trends', ln=True, align='C')
    pdf.ln(10)

    # Semester 1 stats
    y = pdf.get_y()
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(102, 126, 234)
    pdf.cell(140, 8, 'Semester 1', align='C')
    pdf.cell(140, 8, 'Semester 2', align='C', ln=True)
    y = pdf.get_y()

    add_stat_box(pdf, 'Total', r['sem1']['total'], 10, y, 44)
    add_stat_box(pdf, 'Passed', f"{r['sem1']['passed']} ({r['sem1']['pass_pct']}%)", 58, y, 44)
    add_stat_box(pdf, 'Failed', r['sem1']['failed'], 106, y, 44)

    add_stat_box(pdf, 'Total', r['sem2']['total'], 158, y, 44)
    add_stat_box(pdf, 'Passed', f"{r['sem2']['passed']} ({r['sem2']['pass_pct']}%)", 206, y, 44)
    add_stat_box(pdf, 'Failed', r['sem2']['failed'], 254, y, 44)
    pdf.set_y(y + 28)

    y2 = pdf.get_y()
    add_stat_box(pdf, 'Avg SGPA', r['sem1']['avg_sgpa'], 30, y2, 50)
    add_stat_box(pdf, 'Avg Marks', r['sem1']['avg_marks'], 84, y2, 50)
    add_stat_box(pdf, 'Avg SGPA', r['sem2']['avg_sgpa'], 178, y2, 50)
    add_stat_box(pdf, 'Avg Marks', r['sem2']['avg_marks'], 232, y2, 50)
    pdf.set_y(y2 + 30)

    # Charts
    with tempfile.TemporaryDirectory() as tmpdir:
        # Pass rate comparison
        bar1_path = os.path.join(tmpdir, 'pass_compare.png')
        create_bar_chart(
            ['Passed', 'Failed'],
            [r['sem1']['passed'], r['sem1']['failed']],
            [r['sem2']['passed'], r['sem2']['failed']],
            'Semester 1', 'Semester 2',
            'Pass Rate Comparison', bar1_path
        )
        pdf.image(bar1_path, x=30, y=pdf.get_y(), w=120)

        # SGPA comparison
        bar2_path = os.path.join(tmpdir, 'sgpa_compare.png')
        create_single_bar_chart(
            ['Sem 1', 'Sem 2'],
            [r['sem1']['avg_sgpa'], r['sem2']['avg_sgpa']],
            ['#667eea', '#48bb78'],
            'Average SGPA Comparison', bar2_path
        )
        pdf.image(bar2_path, x=160, y=pdf.get_y(), w=120)

    # === PAGE 2: Trends + Table ===
    pdf.add_page()
    add_section_title(pdf, f"Student Trends ({result_data['result']['common_count']} common students)")

    # Trend summary
    pdf.set_font('Helvetica', 'B', 10)
    improved = result_data['result']['improved']
    declined = result_data['result']['declined']
    same = result_data['result']['same']

    pdf.set_text_color(72, 187, 120)
    pdf.cell(80, 8, f"Improved: {improved}", align='C')
    pdf.set_text_color(252, 129, 129)
    pdf.cell(80, 8, f"Declined: {declined}", align='C')
    pdf.set_text_color(236, 201, 75)
    pdf.cell(80, 8, f"Same: {same}", align='C', ln=True)
    pdf.ln(6)

    # Clean trend column for PDF (remove emojis)
    common_clean = common.copy()
    common_clean['TREND'] = common_clean['TREND'].str.replace('📈 ', '', regex=False).str.replace('📉 ', '', regex=False).str.replace('➡️ ', '', regex=False)
    add_table_to_pdf(pdf, common_clean)

    path = os.path.join(UPLOAD_FOLDER, 'compare_output.pdf')
    pdf.output(path)
    return path


def process_file(path):

    df = pd.read_excel(path, header=None)

    df.columns = [
        "HTNO","SUB","NAME","INT","EXT","TOTAL","GRADE","GP","CR"
    ]

    df = df[df["HTNO"].astype(str).str.contains("Q")]

    df["TOTAL"] = pd.to_numeric(df["TOTAL"], errors="coerce")
    df["GP"] = pd.to_numeric(df["GP"], errors="coerce")
    df["CR"] = pd.to_numeric(df["CR"], errors="coerce")

    failed = df[df["GRADE"].isin(["F","Ab"])]["HTNO"].unique()

    df_pass = df[~df["HTNO"].isin(failed)]

    sgpa = df_pass.groupby("HTNO").apply(
        lambda x: (x["GP"]*x["CR"]).sum()/x["CR"].sum()
    ).reset_index(name="SGPA")

    marks = df_pass[df_pass["CR"]>0].groupby("HTNO")["TOTAL"].sum().reset_index(name="TOTAL MARKS")

    result = pd.merge(marks, sgpa)

    result = result.round(2)

    by_marks = result.sort_values("TOTAL MARKS", ascending=False).reset_index(drop=True)
    by_marks.insert(0, "S.No", range(1, len(by_marks)+1))

    by_sgpa = result.sort_values("SGPA", ascending=False).reset_index(drop=True)
    by_sgpa.insert(0, "S.No", range(1, len(by_sgpa)+1))

    failed_df = pd.DataFrame({"S.No": range(1, len(failed)+1), "HTNO": failed})

    # Per-subject average marks across all passed students
    avg_per_student = df_pass[df_pass["CR"]>0].groupby("HTNO")["TOTAL"].mean()
    avg_marks_per_subject = round(avg_per_student.mean(), 2) if len(avg_per_student) > 0 else 0

    return by_marks, by_sgpa, failed_df, avg_marks_per_subject


@app.route("/", methods=["GET","POST"])
def index():

    marks = sgpa = failed = None
    toppers_marks = toppers_sgpa = None
    passed_count = failed_count = 0
    pass_pct = fail_pct = 0.0

    if request.method == "POST":

        file = request.files["file"]

        path = os.path.join(UPLOAD_FOLDER, file.filename)

        file.save(path)

        by_marks, by_sgpa, failed_df, _ = process_file(path)

        marks = by_marks.to_html(classes="table table-bordered table-sm text-center", index=False)

        sgpa = by_sgpa.to_html(classes="table table-bordered table-sm text-center", index=False)

        failed = failed_df.to_html(classes="table table-bordered table-sm text-center", index=False)

        # Top 3 toppers
        top3_marks = by_marks.head(3).copy()
        top3_marks["S.No"] = range(1, len(top3_marks)+1)
        toppers_marks = top3_marks.to_html(classes="table table-bordered table-sm text-center", index=False)

        top3_sgpa = by_sgpa.head(3).copy()
        top3_sgpa["S.No"] = range(1, len(top3_sgpa)+1)
        toppers_sgpa = top3_sgpa.to_html(classes="table table-bordered table-sm text-center", index=False)

        # Pass/Fail counts & percentages
        passed_count = len(by_marks)
        failed_count = len(failed_df)
        total = passed_count + failed_count
        if total > 0:
            pass_pct = round(passed_count / total * 100, 1)
            fail_pct = round(failed_count / total * 100, 1)

        # Generate comprehensive PDF
        generate_single_pdf(by_marks, by_sgpa, failed_df, passed_count, failed_count, pass_pct, fail_pct)

        # Store for download
        global last_single_data
        last_single_data = {
            'by_marks': by_marks, 'by_sgpa': by_sgpa, 'failed_df': failed_df,
            'passed_count': passed_count, 'failed_count': failed_count,
            'pass_pct': pass_pct, 'fail_pct': fail_pct
        }

    return render_template("index.html", marks=marks, sgpa=sgpa, failed=failed,
                           toppers_marks=toppers_marks, toppers_sgpa=toppers_sgpa,
                           passed_count=passed_count, failed_count=failed_count,
                           pass_pct=pass_pct, fail_pct=fail_pct)


@app.route("/compare", methods=["GET","POST"])
def compare():

    result = None

    if request.method == "POST":
        file1 = request.files.get("file1")
        file2 = request.files.get("file2")

        if file1 and file2:
            path1 = os.path.join(UPLOAD_FOLDER, "sem1_" + file1.filename)
            path2 = os.path.join(UPLOAD_FOLDER, "sem2_" + file2.filename)
            file1.save(path1)
            file2.save(path2)

            marks1, sgpa1, failed1, avg_marks1 = process_file(path1)
            marks2, sgpa2, failed2, avg_marks2 = process_file(path2)

            p1 = len(marks1)
            f1 = len(failed1)
            t1 = p1 + f1
            p2 = len(marks2)
            f2 = len(failed2)
            t2 = p2 + f2

            avg_sgpa1 = round(sgpa1["SGPA"].mean(), 2) if len(sgpa1) > 0 else 0
            avg_sgpa2 = round(sgpa2["SGPA"].mean(), 2) if len(sgpa2) > 0 else 0
            # avg_marks already computed per-subject by process_file

            # Find common students and their performance change
            m1 = marks1[["HTNO","TOTAL MARKS"]].rename(columns={"TOTAL MARKS":"MARKS_SEM1"})
            m2 = marks2[["HTNO","TOTAL MARKS"]].rename(columns={"TOTAL MARKS":"MARKS_SEM2"})
            common = pd.merge(m1, m2, on="HTNO", how="inner")
            common["CHANGE"] = common["MARKS_SEM2"] - common["MARKS_SEM1"]
            common["TREND"] = common["CHANGE"].apply(lambda x: "📈 Improved" if x > 0 else ("📉 Declined" if x < 0 else "➡️ Same"))
            common = common.sort_values("CHANGE", ascending=False).reset_index(drop=True)
            common.insert(0, "S.No", range(1, len(common)+1))

            improved = len(common[common["CHANGE"] > 0])
            declined = len(common[common["CHANGE"] < 0])
            same = len(common[common["CHANGE"] == 0])

            common_html = common.to_html(classes="table table-bordered table-sm text-center", index=False)

            result = {
                "sem1": {"passed": p1, "failed": f1, "total": t1,
                         "pass_pct": round(p1/t1*100,1) if t1>0 else 0,
                         "avg_sgpa": avg_sgpa1, "avg_marks": avg_marks1},
                "sem2": {"passed": p2, "failed": f2, "total": t2,
                         "pass_pct": round(p2/t2*100,1) if t2>0 else 0,
                         "avg_sgpa": avg_sgpa2, "avg_marks": avg_marks2},
                "common_html": common_html,
                "improved": improved,
                "declined": declined,
                "same": same,
                "common_count": len(common)
            }

            # Store data for PDF download
            global last_compare_data
            last_compare_data = {
                "marks1": marks1, "marks2": marks2,
                "common": common, "result": result
            }

    return render_template("compare.html", result=result)


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/download")
def download():
    pdf_path = os.path.join(UPLOAD_FOLDER, "output.pdf")
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True, download_name="JNTU_Analysis.pdf")
    return "No analysis available. Please upload and analyze a file first.", 404


@app.route("/download-compare")
def download_compare():
    global last_compare_data
    if not last_compare_data:
        return "No comparison available. Please compare semesters first.", 404

    generate_compare_pdf(last_compare_data)

    return send_file(
        os.path.join(UPLOAD_FOLDER, "compare_output.pdf"),
        as_attachment=True,
        download_name="JNTU_Comparison.pdf"
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
