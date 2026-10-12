"""
ASRA PDF Report Generator
Generates comprehensive landscape A4 PDF reports for ASRA Examination Results
using fpdf2 and Matplotlib (Agg backend).
"""

import os
import re
import tempfile
from fpdf import FPDF
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def sanitize_text(text):
    """Sanitize text to remove emojis or unsupported Latin-1 characters for FPDF."""
    if text is None:
        return ""
    text_str = str(text)
    # Remove emojis and common non-latin characters
    text_str = re.sub(r'[\U00010000-\U0010ffff]', '', text_str)
    # Replace common unicode symbols with ASCII
    replacements = {
        '📈': '', '📉': '', '➡️': '', '✅': '[PASS]', '❌': '[FAIL]',
        '🏆': '', '🎉': '', '🏅': '', '📊': '', '🎓': '', '📁': '',
        '—': '-', '–': '-', '’': "'", '‘': "'", '“': '"', '”': '"'
    }
    for k, v in replacements.items():
        text_str = text_str.replace(k, v)
    # Filter to latin-1 encodable characters
    return text_str.encode('latin-1', 'replace').decode('latin-1')


class AsraReportPDF(FPDF):
    """Extended FPDF class with custom headers and footers."""

    def __init__(self, exam_title="ASRA Examination Analysis", college_name="ASRA"):
        super().__init__(orientation='L', format='A4')
        self.exam_title = sanitize_text(exam_title)
        self.college_name = sanitize_text(college_name)
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(140, 140, 160)
        self.cell(0, 5, f"{self.college_name} RESULTS ANALYZER  |  {self.exam_title}", border=0, align='L')
        self.ln(6)

    def footer(self):
        self.set_y(-12)
        self.set_font('Helvetica', '', 8)
        self.set_text_color(150, 150, 170)
        self.cell(0, 6, f"Page {self.page_no()}", border=0, align='C')


def add_section_title(pdf, title):
    """Add a bold styled section title."""
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(102, 126, 234)
    pdf.cell(0, 8, sanitize_text(title), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def add_stat_box(pdf, label, value, x, y, w=42, h=20, bg_rgb=(245, 247, 252), border_rgb=(210, 215, 230)):
    """Draw a styled KPI stat box."""
    pdf.set_xy(x, y)
    pdf.set_fill_color(*bg_rgb)
    pdf.set_draw_color(*border_rgb)
    pdf.rect(x, y, w, h, 'DF')
    pdf.set_xy(x, y + 2)
    pdf.set_font('Helvetica', '', 7)
    pdf.set_text_color(110, 115, 135)
    pdf.cell(w, 4, sanitize_text(label), align='C')
    pdf.set_xy(x, y + 7)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(w, 9, sanitize_text(str(value)), align='C')


def render_table(pdf, headers, rows, col_widths, align_list=None):
    """Render a styled table with alternating zebra rows and page break handling."""
    if align_list is None:
        align_list = ['C'] * len(headers)

    row_height = 6
    header_height = 7

    # Draw Header
    def draw_header():
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_fill_color(102, 126, 234)
        pdf.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            pdf.cell(col_widths[i], header_height, sanitize_text(h), border=1, align=align_list[i], fill=True)
        pdf.ln()

    draw_header()

    # Draw Rows
    pdf.set_font('Helvetica', '', 7)
    for r_idx, row in enumerate(rows):
        if pdf.get_y() > pdf.h - 22:
            pdf.add_page()
            draw_header()
            pdf.set_font('Helvetica', '', 7)

        if r_idx % 2 == 0:
            pdf.set_fill_color(248, 250, 252)
        else:
            pdf.set_fill_color(255, 255, 255)

        pdf.set_text_color(30, 30, 40)
        for c_idx, cell_value in enumerate(row):
            val_str = sanitize_text(str(cell_value))
            # Clip if too long
            max_chars = int(col_widths[c_idx] * 0.45)
            if len(val_str) > max_chars and max_chars > 5:
                val_str = val_str[:max_chars - 3] + "..."
            pdf.cell(col_widths[c_idx], row_height, val_str, border=1, align=align_list[c_idx], fill=True)
        pdf.ln()


def generate_asra_charts(analysis, tmpdir):
    """Generate Matplotlib charts for embedding in PDF."""
    chart_paths = {}

    kpi = analysis["kpi"]
    passed = kpi["passed_students"]
    failed = kpi["failed_students"]

    # 1. Pass / Fail Pie Chart
    if passed > 0 or failed > 0:
        fig, ax = plt.subplots(figsize=(4, 2.8))
        ax.pie(
            [passed, failed],
            labels=['Passed', 'Failed'],
            colors=['#48bb78', '#fc8181'],
            autopct='%1.1f%%',
            startangle=90,
            textprops={'fontsize': 8, 'weight': 'bold'}
        )
        ax.set_title("Pass / Fail Distribution", fontsize=10, fontweight='bold', color='#1a202c')
        plt.tight_layout()
        pie_path = os.path.join(tmpdir, "pass_fail_pie.png")
        plt.savefig(pie_path, dpi=160, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        chart_paths["pie"] = pie_path

    # 2. Subject Pass Percentage Bar Chart
    subs = analysis["subjects"][:8]  # top 8
    if subs:
        fig, ax = plt.subplots(figsize=(5.5, 2.8))
        codes = [s["code"] for s in subs]
        pcts = [s["pass_pct"] for s in subs]
        bars = ax.bar(codes, pcts, color='#667eea', width=0.55)
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height}%',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 2), textcoords="offset points",
                        ha='center', va='bottom', fontsize=7, fontweight='bold')
        ax.set_ylim(0, 110)
        ax.set_title("Subject Pass Percentage (%)", fontsize=10, fontweight='bold', color='#1a202c')
        ax.tick_params(axis='x', labelsize=8)
        ax.tick_params(axis='y', labelsize=7)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.tight_layout()
        sub_bar_path = os.path.join(tmpdir, "subject_pass_bar.png")
        plt.savefig(sub_bar_path, dpi=160, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        chart_paths["subjects"] = sub_bar_path

    # 3. Grade Distribution Chart
    gdist = analysis.get("grade_distribution", {})
    if gdist:
        fig, ax = plt.subplots(figsize=(4, 2.8))
        grades = list(gdist.keys())[:7]
        counts = [gdist[g] for g in grades]
        colors = ['#48bb78' if g not in ['F', 'AB', 'ABSENT'] else '#fc8181' for g in grades]
        bars = ax.bar(grades, counts, color=colors, width=0.55)
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 2), textcoords="offset points",
                        ha='center', va='bottom', fontsize=7, fontweight='bold')
        ax.set_title("Overall Grade Distribution", fontsize=10, fontweight='bold', color='#1a202c')
        ax.tick_params(axis='both', labelsize=8)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.tight_layout()
        grade_path = os.path.join(tmpdir, "grade_dist.png")
        plt.savefig(grade_path, dpi=160, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        chart_paths["grades"] = grade_path

    return chart_paths


def generate_asra_pdf(analysis, output_path):
    """
    Generates a full landscape A4 PDF report for the ASRA analysis.
    Saves to output_path and returns output_path.
    """
    meta = analysis["metadata"]
    kpi = analysis["kpi"]
    college_name = meta.get("college") or "ASRA"
    exam_title = meta.get("title") or f"{college_name} Result Analysis"

    pdf = AsraReportPDF(exam_title=exam_title, college_name=college_name)

    with tempfile.TemporaryDirectory() as tmpdir:
        chart_paths = generate_asra_charts(analysis, tmpdir)

        # ====================================================
        # PAGE 1: COVER & EXECUTIVE SUMMARY + KPI + CHARTS
        # ====================================================
        pdf.add_page()

        # Banner Title
        pdf.set_font('Helvetica', 'B', 20)
        pdf.set_text_color(102, 126, 234)
        pdf.cell(0, 10, f"{college_name} RESULTS ANALYZER", new_x="LMARGIN", new_y="NEXT", align='C')

        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(0, 6, sanitize_text(exam_title), new_x="LMARGIN", new_y="NEXT", align='C')

        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(120, 130, 150)
        pdf.cell(0, 5, f"Workbook: {sanitize_text(meta.get('filename'))}  |  Total Candidates: {kpi.get('total_students')}", new_x="LMARGIN", new_y="NEXT", align='C')
        pdf.ln(5)

        # 8 KPI Stat Boxes in 2 rows
        row1_y = pdf.get_y()
        box_w = 32
        spacing = 34
        start_x = 10

        add_stat_box(pdf, "TOTAL STUDENTS", kpi["total_students"], start_x, row1_y, box_w)
        add_stat_box(pdf, "PASSED", f"{kpi['passed_students']} ({kpi['pass_pct']}%)", start_x + spacing, row1_y, box_w, bg_rgb=(240, 253, 244))
        add_stat_box(pdf, "FAILED", f"{kpi['failed_students']} ({kpi['fail_pct']}%)", start_x + spacing * 2, row1_y, box_w, bg_rgb=(254, 242, 242))
        add_stat_box(pdf, "ABSENT", kpi["absent_students"], start_x + spacing * 3, row1_y, box_w)
        add_stat_box(pdf, "AVG SGPA", kpi["avg_sgpa"], start_x + spacing * 4, row1_y, box_w)
        add_stat_box(pdf, "HIGHEST MARKS", kpi["highest_marks"], start_x + spacing * 5, row1_y, box_w)
        add_stat_box(pdf, "HIGHEST SGPA", kpi["highest_sgpa"], start_x + spacing * 6, row1_y, box_w)
        add_stat_box(pdf, "SUBJECTS", kpi["subjects_count"], start_x + spacing * 7, row1_y, box_w)

        pdf.set_y(row1_y + 26)

        # Embed Charts side-by-side
        chart_y = pdf.get_y()
        if "pie" in chart_paths and os.path.exists(chart_paths["pie"]):
            pdf.image(chart_paths["pie"], x=12, y=chart_y, w=82)
        if "subjects" in chart_paths and os.path.exists(chart_paths["subjects"]):
            pdf.image(chart_paths["subjects"], x=98, y=chart_y, w=105)
        if "grades" in chart_paths and os.path.exists(chart_paths["grades"]):
            pdf.image(chart_paths["grades"], x=206, y=chart_y, w=80)

        # ====================================================
        # PAGE 2: TOPPER RANKINGS
        # ====================================================
        pdf.add_page()
        add_section_title(pdf, "Top Toppers by Total Marks (Eligible Passed Students)")

        toppers_marks = analysis["toppers_marks"]["all"][:10]
        if toppers_marks:
            headers = ["Rank", "S.No", "Hall Ticket No", "Total Marks", "SGPA", "Subjects Passed"]
            widths = [22, 22, 65, 50, 45, 55]
            rows = []
            for tm in toppers_marks:
                rows.append([
                    f"#{tm['rank']}",
                    tm['s_no'],
                    tm['HTNO'],
                    tm['total_marks'],
                    tm['sgpa'],
                    f"{tm['passed_count']} / {tm['subjects_count']}"
                ])
            render_table(pdf, headers, rows, widths)
        else:
            pdf.set_font('Helvetica', 'I', 9)
            pdf.cell(0, 8, "No eligible topper students recorded.", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(8)
        add_section_title(pdf, "Top Toppers by SGPA (Eligible Passed Students)")

        toppers_sgpa = analysis["toppers_sgpa"]["all"][:10]
        if toppers_sgpa:
            headers = ["Rank", "S.No", "Hall Ticket No", "SGPA", "Total Marks", "Subjects Passed"]
            widths = [22, 22, 65, 45, 50, 55]
            rows = []
            for ts in toppers_sgpa:
                rows.append([
                    f"#{ts['rank']}",
                    ts['s_no'],
                    ts['HTNO'],
                    ts['sgpa'],
                    ts['total_marks'],
                    f"{ts['passed_count']} / {ts['subjects_count']}"
                ])
            render_table(pdf, headers, rows, widths)
        else:
            pdf.set_font('Helvetica', 'I', 9)
            pdf.cell(0, 8, "No eligible topper students recorded.", new_x="LMARGIN", new_y="NEXT")

        # ====================================================
        # PAGE 3: SUBJECT-WISE PERFORMANCE ANALYSIS
        # ====================================================
        pdf.add_page()
        add_section_title(pdf, "Subject-Wise Performance Analysis")

        subs = analysis["subjects"]
        if subs:
            headers = ["Sub Code", "Subject Name", "Appeared", "Passed", "Failed", "Pass %", "Avg Marks", "Max", "Min", "Avg GP"]
            widths = [26, 90, 20, 18, 18, 20, 22, 16, 16, 18]
            aligns = ['C', 'L', 'C', 'C', 'C', 'C', 'C', 'C', 'C', 'C']
            rows = []
            for s in subs:
                rows.append([
                    s["code"],
                    s["name"],
                    s["appeared"],
                    s["passed"],
                    s["failed"],
                    f"{s['pass_pct']}%",
                    s["avg_marks"],
                    s["max_marks"],
                    s["min_marks"],
                    s["avg_gp"]
                ])
            render_table(pdf, headers, rows, widths, align_list=aligns)

        # ====================================================
        # PAGE 4+: COMPLETE STUDENT RESULTS
        # ====================================================
        pdf.add_page()
        add_section_title(pdf, "Complete Student Results (All Candidates)")

        all_students = analysis["complete_students"]
        if all_students:
            headers = ["S.No", "Hall Ticket No", "Subjects", "Passed", "Failed", "Total Marks", "SGPA", "Result Status"]
            widths = [18, 55, 30, 28, 28, 42, 35, 40]
            rows = []
            for st in all_students:
                status_label = "[PASS]" if st["is_passed"] else "[FAIL]"
                rows.append([
                    st["s_no"],
                    st["HTNO"],
                    st["subjects_count"],
                    st["passed_count"],
                    st["failed_count"],
                    st["total_marks"],
                    st["sgpa"],
                    status_label
                ])
            render_table(pdf, headers, rows, widths)

        # ====================================================
        # FAILED STUDENTS LIST
        # ====================================================
        failed_students = analysis["failed_students"]
        if failed_students:
            pdf.add_page()
            add_section_title(pdf, f"Failed Candidates Analysis ({len(failed_students)} Students)")

            headers = ["S.No", "Hall Ticket No", "Failed Count", "Failed Subject Names"]
            widths = [18, 55, 30, 165]
            aligns = ['C', 'C', 'C', 'L']
            rows = []
            for idx, fst in enumerate(failed_students, 1):
                subs_detail_parts = []
                for sub_idx, fs in enumerate(fst.get("failed_subjects", []), 1):
                    sub_name = fs.get("name") or fs.get("code")
                    subs_detail_parts.append(f"{sub_idx}. {sub_name}")
                subs_detail_str = "; ".join(subs_detail_parts)
                rows.append([
                    idx,
                    fst["HTNO"],
                    fst["failed_count"],
                    subs_detail_str
                ])
            render_table(pdf, headers, rows, widths, align_list=aligns)

        # ====================================================
        # CALCULATION METHODOLOGY & NOTES
        # ====================================================
        pdf.add_page()
        add_section_title(pdf, "Calculation Methodology, Regulations & Assumptions")

        pdf.set_font('Helvetica', '', 8)
        pdf.set_text_color(40, 50, 70)
        assumptions = analysis.get("assumptions", [])
        for a in assumptions:
            pdf.cell(5, 5, "-")
            pdf.multi_cell(0, 5, sanitize_text(a))
            pdf.ln(1)

        pdf.ln(5)
        pdf.set_font('Helvetica', 'I', 8)
        pdf.set_text_color(120, 120, 140)
        pdf.multi_cell(
            0, 5,
            "Notice: This report is automatically compiled by the JNTUH Result & Topper Analyzer (ASRA Module) "
            "for internal academic analysis, faculty appraisal, and student performance tracking. "
            "Official university grade memos and marks cards issued by JNTU Hyderabad take legal precedence."
        )

        pdf.output(output_path)

    return output_path
