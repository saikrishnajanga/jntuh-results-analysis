# 🎓 JNTU Topper Analyzer Web App

A professional web application built using **Flask (Python)** to analyze JNTU result Excel files and generate **accurate topper lists based on Total Marks and SGPA**.

---

# 🚀 Features

✅ Upload JNTU result Excel file (.xlsx)
✅ Ranking by **Total Marks**
✅ Ranking by **SGPA**
✅ Separate **Failed Students List**
✅ Automatic **Serial Numbers (S.No)**
✅ Clean and professional UI
✅ Download result as Excel file
✅ Export as PDF (via browser)
✅ Works on desktop and online

---

# 🖥️ Technologies Used

* Python 3
* Flask
* Pandas
* OpenPyXL
* HTML
* Bootstrap 5

---

# 📁 Project Structure

```
jntu_web_app_v2/
│
├── app.py
├── requirements.txt
├── render.yaml
├── README.md
│
├── templates/
│     └── index.html
│
└── uploads/
```

---

# ⚙️ Installation (Local Setup)

## Step 1: Download Project

Clone repository:

```
git clone https://github.com/yourusername/jntu-topper-analyzer.git
```

or download ZIP and extract.

---

## Step 2: Install Requirements

Open terminal inside project folder:

```
pip install -r requirements.txt
```

---

## Step 3: Run Application

```
python app.py
```

---

## Step 4: Open Browser

Go to:

```
http://127.0.0.1:5000
```

---

# 🌐 Usage

1. Click **Upload Excel**

2. Select JNTU result file

3. View:

   * Ranking by Marks
   * Ranking by SGPA
   * Failed Students

4. Click **Download Excel** to save result

---

# 📊 SGPA Calculation Formula

```
SGPA = Σ (Grade Points × Credits) / Σ Credits
```

Failed subjects are excluded.

---

# 📤 Deployment

This app can be hosted on:

* Render
* Railway
* PythonAnywhere

---

# 🎯 Example Output

## Ranking by Marks

| S.No | HTNO       | Total Marks | SGPA |
| ---- | ---------- | ----------- | ---- |
| 1    | 23Q61A6610 | 793         | 8.90 |

---

## Ranking by SGPA

| S.No | HTNO | SGPA | Total Marks |
| ---- | ---- | ---- | ----------- |
s
---

# 👨‍💻 Author

Sai
B.Tech CSE (AI & ML)

---

# 📄 License

This project is for educational purposes.

---

# ⭐ Support

If you like this project, give it a star on GitHub ⭐
