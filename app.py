from flask import Flask, render_template, request, send_file, jsonify
import pandas as pd
import os

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


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

    return by_marks, by_sgpa, failed_df


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

        by_marks, by_sgpa, failed_df = process_file(path)

        by_marks.to_excel("uploads/output.xlsx", index=False)

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

            marks1, sgpa1, failed1 = process_file(path1)
            marks2, sgpa2, failed2 = process_file(path2)

            p1 = len(marks1)
            f1 = len(failed1)
            t1 = p1 + f1
            p2 = len(marks2)
            f2 = len(failed2)
            t2 = p2 + f2

            avg_sgpa1 = round(sgpa1["SGPA"].mean(), 2) if len(sgpa1) > 0 else 0
            avg_sgpa2 = round(sgpa2["SGPA"].mean(), 2) if len(sgpa2) > 0 else 0
            avg_marks1 = round(marks1["TOTAL MARKS"].mean(), 2) if len(marks1) > 0 else 0
            avg_marks2 = round(marks2["TOTAL MARKS"].mean(), 2) if len(marks2) > 0 else 0

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

    return render_template("compare.html", result=result)


@app.route("/download")
def download():
    return send_file("uploads/output.xlsx", as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
