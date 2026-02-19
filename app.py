from flask import Flask, render_template, request, send_file
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

    if request.method == "POST":

        file = request.files["file"]

        path = os.path.join(UPLOAD_FOLDER, file.filename)

        file.save(path)

        by_marks, by_sgpa, failed_df = process_file(path)

        by_marks.to_excel("uploads/output.xlsx", index=False)

        marks = by_marks.to_html(classes="table table-bordered table-sm text-center", index=False)

        sgpa = by_sgpa.to_html(classes="table table-bordered table-sm text-center", index=False)

        failed = failed_df.to_html(classes="table table-bordered table-sm text-center", index=False)

    return render_template("index.html", marks=marks, sgpa=sgpa, failed=failed)


@app.route("/download")
def download():
    return send_file("uploads/output.xlsx", as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
