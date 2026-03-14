from flask import Flask, render_template, request, send_file, jsonify
import pandas as pd
import os
from fpdf import FPDF

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Store last compare result for PDF download
last_compare_data = {}


def generate_pdf(dataframes_with_titles, filename):
    """Generate a PDF with multiple tables from dataframes."""
    pdf = FPDF(orientation='L', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)

    for title, df in dataframes_with_titles:
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 16)
        pdf.set_text_color(102, 126, 234)
        pdf.cell(0, 12, title, ln=True, align='C')
        pdf.ln(4)

        cols = list(df.columns)
        col_count = len(cols)
        page_width = pdf.w - 20  # margins
        col_width = page_width / col_count

        # Header
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_fill_color(102, 126, 234)
        pdf.set_text_color(255, 255, 255)
        for col in cols:
            pdf.cell(col_width, 8, str(col), border=1, align='C', fill=True)
        pdf.ln()

        # Rows
        pdf.set_font('Helvetica', '', 8)
        pdf.set_text_color(30, 30, 30)
        for i, (_, row) in enumerate(df.iterrows()):
            if i % 2 == 0:
                pdf.set_fill_color(245, 247, 250)
            else:
                pdf.set_fill_color(255, 255, 255)
            for col in cols:
                pdf.cell(col_width, 7, str(row[col]), border=1, align='C', fill=True)
            pdf.ln()

    path = os.path.join(UPLOAD_FOLDER, filename)
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

        generate_pdf([
            ("Top Students by Total Marks", by_marks),
            ("Top Students by SGPA", by_sgpa),
            ("Failed Students", failed_df)
        ], "output.pdf")

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

    r = last_compare_data["result"]

    # Create summary dataframe
    summary = pd.DataFrame({
        "Metric": ["Total Students", "Passed", "Failed", "Pass %", "Avg SGPA", "Avg Marks"],
        "Semester 1": [r["sem1"]["total"], r["sem1"]["passed"], r["sem1"]["failed"],
                       f"{r['sem1']['pass_pct']}%", r["sem1"]["avg_sgpa"], r["sem1"]["avg_marks"]],
        "Semester 2": [r["sem2"]["total"], r["sem2"]["passed"], r["sem2"]["failed"],
                       f"{r['sem2']['pass_pct']}%", r["sem2"]["avg_sgpa"], r["sem2"]["avg_marks"]]
    })

    common = last_compare_data["common"]

    generate_pdf([
        ("Semester Comparison Summary", summary),
        ("Student Performance Trends", common)
    ], "compare_output.pdf")

    return send_file(
        os.path.join(UPLOAD_FOLDER, "compare_output.pdf"),
        as_attachment=True,
        download_name="JNTU_Comparison.pdf"
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
