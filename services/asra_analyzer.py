"""
ASRA Result Analysis Engine
Provides robust Excel parsing, header detection, student-level aggregation,
SGPA calculations, topper rankings, and subject-wise analytics for PT-series JNTUH results.
"""

import os
import re
import openpyxl
import pandas as pd
import numpy as np


COLUMN_ALIASES = {
    "HTNO": ["HTNO", "HALL TICKET NO", "HALL TICKET", "ROLL NO", "REG NO", "H.T.NO", "HT NUMBER"],
    "SUBJECT_CODE": ["SUBJECT_CODE", "SUB_CODE", "SUB CODE", "SUB", "SUBJECT", "SUBJECTCODE", "SUBCODE"],
    "SUBJECT_NAME": ["SUBJECT_NAME", "SUB_NAME", "NAME", "SUBJECT TITLE", "SUBNAME", "SUBJECTNAME"],
    "INTERNALMARKS": ["INTERNALMARKS", "INTERNAL MARKS", "INT", "INTERNAL", "INT_MARKS", "INT MARKS"],
    "EXTERNALMARKS": ["EXTERNALMARKS", "EXTERNAL MARKS", "EXT", "EXTERNAL", "EXT_MARKS", "EXT MARKS"],
    "TOTALMARKS": ["TOTALMARKS", "TOTAL MARKS", "TOTAL", "TOT", "MARKS", "TOTAL_MARKS"],
    "GRADE": ["GRADE", "LETTER_GRADE", "LETTER GRADE", "GRD", "GRADE_LETTER"],
    "GRADE_POINTS": ["GRADE_POINTS", "GRADE POINTS", "GP", "POINTS", "GRADE_POINT", "GRADEPOINT"],
    "CREDITS": ["CREDITS", "CREDIT", "CR", "CRS", "COURSE_CREDITS"]
}


def extract_metadata_from_text_and_name(intro_rows, filename=""):
    """Extract semester, cohort, regulation, and examination title."""
    meta = {
        "title": "JNTUH Examination Results",
        "semester": "",
        "regulation": "",
        "date_info": "",
        "filename": os.path.basename(filename) if filename else ""
    }

    # Extract from filename
    fn = os.path.basename(filename)
    sem_match = re.search(r"([I|V|X]+)\s*B\.Tech\.?\s*([I|V|X]+)\s*Semester", fn, re.IGNORECASE)
    if sem_match:
        meta["semester"] = f"{sem_match.group(1)} B.Tech. {sem_match.group(2)} Semester"
    
    reg_match = re.search(r"\((R\d+)\)", fn, re.IGNORECASE)
    if reg_match:
        meta["regulation"] = reg_match.group(1).upper()
        
    type_match = re.search(r"(Regular|Supplementary)", fn, re.IGNORECASE)
    exam_type = type_match.group(1) if type_match else ""

    parts = [meta["semester"], f"({meta['regulation']})" if meta["regulation"] else "", exam_type]
    constructed_title = " ".join([p for p in parts if p]).strip()
    if constructed_title:
        meta["title"] = constructed_title

    # Extract date from introductory rows
    for row in intro_rows:
        text = " ".join([str(c) for c in row if c is not None])
        if "Date" in text or "IST" in text:
            meta["date_info"] = text.strip()
            break

    return meta


def detect_headers_and_extract_data(file_path):
    """
    Scans workbook rows to detect the true header row and introductory content.
    Returns: (headers, data_rows, intro_rows, warnings)
    """
    warnings = []
    wb = openpyxl.load_workbook(file_path, data_only=True)
    sheet = wb.active
    raw_rows = [list(r) for r in sheet.iter_rows(values_only=True)]
    
    if not raw_rows:
        raise ValueError("The uploaded Excel workbook contains no data or is empty.")

    header_row_idx = None
    best_match_count = 0

    for idx, row in enumerate(raw_rows[:25]):
        if not row:
            continue
        cleaned_cells = [str(c).strip().upper() for c in row if c is not None]
        matches = 0
        for std_col, aliases in COLUMN_ALIASES.items():
            if any(alias in cleaned_cells for alias in aliases):
                matches += 1
        
        # HTNO must be present in a legitimate header row
        has_htno = any(any(alias in str(c).strip().upper() for alias in COLUMN_ALIASES["HTNO"]) for c in row if c is not None)
        
        if has_htno and matches >= 3 and matches > best_match_count:
            best_match_count = matches
            header_row_idx = idx

    if header_row_idx is None:
        raise ValueError(
            "Could not identify the header row in the workbook. "
            "Please ensure the file contains columns for HTNO, SUBJECT_CODE, TOTALMARKS, GRADE, etc."
        )

    intro_rows = raw_rows[:header_row_idx]
    detected_headers = [str(c).strip() if c is not None else f"COL_{i}" for i, c in enumerate(raw_rows[header_row_idx])]
    data_rows = raw_rows[header_row_idx + 1:]

    return detected_headers, data_rows, intro_rows, warnings


def map_columns(headers):
    """Maps workbook headers to standard internal column names."""
    col_mapping = {}
    used_standards = set()

    for idx, col_name in enumerate(headers):
        normalized = col_name.strip().upper()
        matched_std = None
        for std_col, aliases in COLUMN_ALIASES.items():
            if std_col not in used_standards and any(alias == normalized or alias in normalized for alias in aliases):
                matched_std = std_col
                used_standards.add(std_col)
                break
        if matched_std:
            col_mapping[col_name] = matched_std
        else:
            col_mapping[col_name] = col_name

    # Validate essential columns
    required = ["HTNO", "TOTALMARKS", "GRADE"]
    missing = [req for req in required if req not in col_mapping.values()]
    if missing:
        raise ValueError(f"Required columns missing from file: {', '.join(missing)}. Detected columns: {list(col_mapping.keys())}")

    return col_mapping


def analyze_asra_results(file_path, selected_cohort=None, college="ASRA"):
    """
    Core processing engine for ASRA (PT series) and AVIH (Q series) examination analysis.
    
    Returns a structured dictionary with:
    - metadata, kpi_stats, toppers_marks, toppers_sgpa,
    - complete_students, failed_students, absent_students,
    - subjects_analytics, grade_distribution, marks_distribution,
    - sgpa_distribution, cohorts, warnings, assumptions
    """
    raw_headers, raw_data, intro_rows, warnings = detect_headers_and_extract_data(file_path)
    col_map = map_columns(raw_headers)
    meta = extract_metadata_from_text_and_name(intro_rows, file_path)

    df = pd.DataFrame(raw_data, columns=raw_headers)
    df = df.rename(columns=col_map)

    # 1. Drop completely empty rows
    df = df.dropna(how="all").reset_index(drop=True)

    # 2. Drop repeated headers if any row has HTNO matching header name
    df = df[df["HTNO"].astype(str).str.strip().str.upper() != "HTNO"].reset_index(drop=True)

    # 3. Clean string columns
    for str_col in ["HTNO", "SUBJECT_CODE", "SUBJECT_NAME", "GRADE"]:
        if str_col in df.columns:
            df[str_col] = df[str_col].astype(str).str.strip()

    # 4. College / Campus Series Filtering (ASRA: PT series, AVIH: Q series)
    college_mode = str(college).upper().strip() if college else "ASRA"
    if college_mode not in ["ASRA", "AVIH"]:
        college_mode = "ASRA"

    if college_mode == "AVIH":
        primary_pattern = "Q"
        college_label = "AVIH"
        college_title = "AVIH (Aurora's Technological and Research Institute)"
    else:
        primary_pattern = "PT"
        college_label = "ASRA"
        college_title = "ASRA (Aurora's Scientific Technological and Research Academy)"

    # Auto-detection: if file contains the alternate pattern, switch gracefully
    has_primary = df["HTNO"].astype(str).str.upper().str.contains(primary_pattern).any()
    if not has_primary:
        alternate_pattern = "PT" if primary_pattern == "Q" else "Q"
        if df["HTNO"].astype(str).str.upper().str.contains(alternate_pattern).any():
            primary_pattern = alternate_pattern
            college_label = "ASRA" if primary_pattern == "PT" else "AVIH"
            college_title = "ASRA (Aurora's Scientific Technological and Research Academy)" if primary_pattern == "PT" else "AVIH (Aurora's Technological and Research Institute)"
            warnings.append(f"Auto-switched campus mode to {college_label} based on uploaded marksheet Hall Ticket identifiers.")

    series_mask = df["HTNO"].astype(str).str.upper().str.contains(primary_pattern)
    non_series_count = (~series_mask).sum()
    if non_series_count > 0:
        warnings.append(f"Excluded {non_series_count} records not matching {college_label} series ({primary_pattern}).")
    df = df[series_mask].reset_index(drop=True)

    if df.empty:
        raise ValueError(f"No valid {college_label} examination records found in the uploaded file.")

    meta["college"] = college_label
    meta["college_full"] = college_title
    meta["series_pattern"] = primary_pattern

    # 5. Detect cohorts
    df["COHORT"] = df["HTNO"].apply(lambda h: h[:4].upper() if len(h) >= 4 else "OTHER")
    available_cohorts = sorted(df["COHORT"].unique().tolist())

    # Optional cohort filtering
    if selected_cohort and selected_cohort != "ALL":
        if selected_cohort in available_cohorts:
            df = df[df["COHORT"] == selected_cohort].reset_index(drop=True)
            warnings.append(f"Filtered analysis to cohort: {selected_cohort}")
        else:
            warnings.append(f"Cohort {selected_cohort} not found. Analyzing all available cohorts.")

    # 6. Numeric conversions
    for num_col in ["TOTALMARKS", "GRADE_POINTS", "CREDITS", "INTERNALMARKS", "EXTERNALMARKS"]:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce")
        else:
            df[num_col] = 0.0

    # Fill NaN safely
    df["TOTALMARKS"] = df["TOTALMARKS"].fillna(0.0)
    df["GRADE_POINTS"] = df["GRADE_POINTS"].fillna(0.0)
    df["CREDITS"] = df["CREDITS"].fillna(0.0)

    # 7. Check for duplicate records (same student + subject code)
    dup_mask = df.duplicated(subset=["HTNO", "SUBJECT_CODE"], keep=False)
    if dup_mask.any():
        dup_count = dup_mask.sum()
        warnings.append(f"Found {dup_count} duplicate student-subject records. Using highest marks per subject.")
        df = df.sort_values("TOTALMARKS", ascending=False).drop_duplicates(subset=["HTNO", "SUBJECT_CODE"], keep="first").reset_index(drop=True)

    # 8. Grade normalization & classification
    df["GRADE_NORM"] = df["GRADE"].str.upper().str.strip()
    failure_grades = ["F", "AB", "ABSENT", "FAIL"]
    absent_grades = ["AB", "ABSENT"]

    # 9. Student-level aggregation
    student_summaries = []
    failed_student_records = []
    absent_student_records = []

    for htno, student_df in df.groupby("HTNO"):
        cohort = student_df["COHORT"].iloc[0]
        sub_count = len(student_df)
        
        # Total marks across all applicable subjects
        total_marks = round(float(student_df["TOTALMARKS"].sum()), 2)
        
        # Failed & Absent subjects
        failed_rows = student_df[student_df["GRADE_NORM"].isin(failure_grades)]
        absent_rows = student_df[student_df["GRADE_NORM"].isin(absent_grades)]
        
        failed_count = len(failed_rows)
        absent_count = len(absent_rows)
        passed_count = sub_count - failed_count
        
        is_passed = (failed_count == 0)
        status = "Passed" if is_passed else ("Absent" if absent_count > 0 and passed_count == 0 else "Failed")

        # Credits & SGPA
        # In JNTU, SGPA = Sum(GP * CR) / Sum(CR) for subjects where CR > 0.
        # Zero-credit subjects (audit courses) are excluded from the denominator.
        credit_subjects = student_df[student_df["CREDITS"] > 0]
        cr_sum = credit_subjects["CREDITS"].sum()
        weighted_gp = (credit_subjects["GRADE_POINTS"] * credit_subjects["CREDITS"]).sum()
        
        if cr_sum > 0:
            sgpa = round(float(weighted_gp / cr_sum), 2)
        else:
            sgpa = 0.0

        # Credits earned = credits of passed subjects
        passed_subjects = student_df[~student_df["GRADE_NORM"].isin(failure_grades)]
        credits_earned = round(float(passed_subjects["CREDITS"].sum()), 1)
        credits_attempted = round(float(cr_sum), 1)

        failed_subs_detail = []
        for _, frow in failed_rows.iterrows():
            failed_subs_detail.append({
                "code": frow.get("SUBJECT_CODE", ""),
                "name": frow.get("SUBJECT_NAME", ""),
                "grade": frow.get("GRADE", ""),
                "marks": frow.get("TOTALMARKS", 0)
            })

        summary = {
            "HTNO": htno,
            "cohort": cohort,
            "subjects_count": sub_count,
            "total_marks": total_marks,
            "credits_attempted": credits_attempted,
            "credits_earned": credits_earned,
            "sgpa": sgpa,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "absent_count": absent_count,
            "status": status,
            "is_passed": is_passed,
            "failed_subjects": failed_subs_detail
        }
        student_summaries.append(summary)

        if not is_passed:
            failed_student_records.append(summary)
            if absent_count > 0:
                absent_student_records.append(summary)

    students_df = pd.DataFrame(student_summaries)
    if students_df.empty:
        raise ValueError("No students could be evaluated from the dataset.")

    total_students = len(students_df)
    passed_students_count = len(students_df[students_df["is_passed"]])
    failed_students_count = total_students - passed_students_count
    absent_students_count = len(absent_student_records)

    pass_pct = round((passed_students_count / total_students) * 100, 1) if total_students > 0 else 0.0
    fail_pct = round((failed_students_count / total_students) * 100, 1) if total_students > 0 else 0.0

    # 10. Topper Rankings (Only eligible passed students)
    eligible_df = students_df[students_df["is_passed"]].copy()

    # Ranking by Total Marks (Dense ranking)
    if not eligible_df.empty:
        by_marks = eligible_df.sort_values(by=["total_marks", "sgpa"], ascending=[False, False]).reset_index(drop=True)
        by_marks["rank"] = by_marks["total_marks"].rank(ascending=False, method="min").astype(int)
        by_marks["s_no"] = range(1, len(by_marks) + 1)
        toppers_marks_all = by_marks.to_dict(orient="records")
        toppers_marks_top3 = toppers_marks_all[:3]

        # Ranking by SGPA (Dense ranking)
        by_sgpa = eligible_df.sort_values(by=["sgpa", "total_marks"], ascending=[False, False]).reset_index(drop=True)
        by_sgpa["rank"] = by_sgpa["sgpa"].rank(ascending=False, method="min").astype(int)
        by_sgpa["s_no"] = range(1, len(by_sgpa) + 1)
        toppers_sgpa_all = by_sgpa.to_dict(orient="records")
        toppers_sgpa_top3 = toppers_sgpa_all[:3]

        avg_sgpa = round(float(eligible_df["sgpa"].mean()), 2)
        highest_marks = float(eligible_df["total_marks"].max())
        highest_sgpa = float(eligible_df["sgpa"].max())
    else:
        toppers_marks_all = []
        toppers_marks_top3 = []
        toppers_sgpa_all = []
        toppers_sgpa_top3 = []
        avg_sgpa = 0.0
        highest_marks = 0.0
        highest_sgpa = 0.0

    # Assign overall ranks across all students for Complete Results table
    students_df_sorted = students_df.sort_values(by=["is_passed", "total_marks"], ascending=[False, False]).reset_index(drop=True)
    students_df_sorted["s_no"] = range(1, len(students_df_sorted) + 1)
    complete_students_list = students_df_sorted.to_dict(orient="records")

    # 11. Subject-Wise Analytics
    subject_analytics = []
    for sub_code, sub_group in df.groupby("SUBJECT_CODE"):
        sub_name = sub_group["SUBJECT_NAME"].iloc[0] if "SUBJECT_NAME" in sub_group.columns else sub_code
        appeared = len(sub_group)
        sub_failed = len(sub_group[sub_group["GRADE_NORM"].isin(failure_grades)])
        sub_absent = len(sub_group[sub_group["GRADE_NORM"].isin(absent_grades)])
        sub_passed = appeared - sub_failed
        sub_pass_pct = round((sub_passed / appeared) * 100, 1) if appeared > 0 else 0.0

        valid_marks = sub_group["TOTALMARKS"]
        avg_m = round(float(valid_marks.mean()), 2) if appeared > 0 else 0.0
        max_m = float(valid_marks.max()) if appeared > 0 else 0.0
        min_m = float(valid_marks.min()) if appeared > 0 else 0.0
        avg_gp = round(float(sub_group["GRADE_POINTS"].mean()), 2) if appeared > 0 else 0.0

        # Grade distribution for this subject
        grade_dist = sub_group["GRADE_NORM"].value_counts().to_dict()

        subject_analytics.append({
            "code": sub_code,
            "name": sub_name,
            "appeared": appeared,
            "passed": sub_passed,
            "failed": sub_failed,
            "absent": sub_absent,
            "pass_pct": sub_pass_pct,
            "avg_marks": avg_m,
            "max_marks": max_m,
            "min_marks": min_m,
            "avg_gp": avg_gp,
            "grade_distribution": grade_dist
        })

    subject_analytics.sort(key=lambda s: s["pass_pct"], reverse=True)

    # 12. Overall Grade Distribution
    grade_distribution = df["GRADE_NORM"].value_counts().to_dict()

    # 13. Marks and SGPA distribution buckets
    marks_bins = {"< 400": 0, "400 - 499": 0, "500 - 599": 0, "600+": 0}
    for m in students_df["total_marks"]:
        if m < 400:
            marks_bins["< 400"] += 1
        elif m < 500:
            marks_bins["400 - 499"] += 1
        elif m < 600:
            marks_bins["500 - 599"] += 1
        else:
            marks_bins["600+"] += 1

    sgpa_bins = {"< 6.0": 0, "6.0 - 6.99": 0, "7.0 - 7.99": 0, "8.0 - 8.99": 0, "9.0+": 0}
    for s in eligible_df["sgpa"] if not eligible_df.empty else []:
        if s < 6.0:
            sgpa_bins["< 6.0"] += 1
        elif s < 7.0:
            sgpa_bins["6.0 - 6.99"] += 1
        elif s < 8.0:
            sgpa_bins["7.0 - 7.99"] += 1
        elif s < 9.0:
            sgpa_bins["8.0 - 8.99"] += 1
        else:
            sgpa_bins["9.0+"] += 1

    # 14. Documented Assumptions
    assumptions = [
        f"Campus Filter: Evaluates all {college_label} candidate examination records.",
        "Total Marks: Sum of validated TOTALMARKS across all applicable registered subjects.",
        "Pass/Fail Policy: Students with any Grade in ['F', 'AB', 'ABSENT'] are classified as Failed.",
        "SGPA Calculation: Weighted formula Sum(GP * Credits) / Sum(Credits), excluding zero-credit audit courses.",
        "Topper Eligibility: Strictly restricted to students who passed all registered subjects in the examination.",
        "Provisional Status: SGPA calculated locally for reference and analysis; official university transcripts take precedence."
    ]

    return {
        "metadata": meta,
        "kpi": {
            "total_students": total_students,
            "passed_students": passed_students_count,
            "failed_students": failed_students_count,
            "absent_students": absent_students_count,
            "pass_pct": pass_pct,
            "fail_pct": fail_pct,
            "avg_sgpa": avg_sgpa,
            "highest_marks": highest_marks,
            "highest_sgpa": highest_sgpa,
            "eligible_toppers_count": len(eligible_df),
            "subjects_count": len(subject_analytics),
            "total_records_processed": len(df),
            "college": college_label,
            "college_full": college_title,
            "selected_cohort": selected_cohort or "ALL",
            "available_cohorts": available_cohorts
        },
        "toppers_marks": {
            "top3": toppers_marks_top3,
            "all": toppers_marks_all
        },
        "toppers_sgpa": {
            "top3": toppers_sgpa_top3,
            "all": toppers_sgpa_all
        },
        "complete_students": complete_students_list,
        "failed_students": failed_student_records,
        "absent_students": absent_student_records,
        "subjects": subject_analytics,
        "grade_distribution": grade_distribution,
        "marks_distribution": marks_bins,
        "sgpa_distribution": sgpa_bins,
        "warnings": warnings,
        "assumptions": assumptions
    }
