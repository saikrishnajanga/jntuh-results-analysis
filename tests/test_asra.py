"""
Comprehensive Unit & Integration Test Suite for JNTUH Result & Topper Analyzer (ASRA Module)
Tests:
- Header detection and normalization
- PT-Series filtering and cohort extraction
- Aggregation, SGPA calculation, Total marks, Pass/Fail classifications
- Topper rankings and tie handling
- Subject analytics and grade distributions
- PDF generation and isolation
- Flask routes (/asra, /download-asra, /health, /, /compare)
"""

import os
import unittest
import pandas as pd
import openpyxl
from io import BytesIO

from app import app
from services.asra_analyzer import (
    detect_headers_and_extract_data,
    map_columns,
    analyze_asra_results
)
from services.asra_pdf import generate_asra_pdf, sanitize_text


class TestASRAAnalyzer(unittest.TestCase):

    def setUp(self):
        self.ref_file = os.path.join("uploads", "PT-66-III B.Tech. II Semester (R22) Regular.xlsx")
        self.app = app.test_client()
        self.app.testing = True

    def test_header_detection_reference_file(self):
        """Test header detection on the reference workbook with intro lines."""
        headers, data_rows, intro_rows, warnings = detect_headers_and_extract_data(self.ref_file)
        self.assertIn("HTNO", headers)
        self.assertIn("SUBJECT_CODE", headers)
        self.assertIn("TOTALMARKS", headers)
        self.assertIn("GRADE", headers)
        self.assertEqual(len(intro_rows), 2)
        self.assertGreater(len(data_rows), 90)

    def test_column_mapping(self):
        """Test mapping of diverse column aliases."""
        headers = ["H.T.NO", "SUB_CODE", "SUB_NAME", "INT_MARKS", "EXT_MARKS", "TOTAL", "GRADE_LETTER", "GP", "CR"]
        col_map = map_columns(headers)
        self.assertEqual(col_map["H.T.NO"], "HTNO")
        self.assertEqual(col_map["SUB_CODE"], "SUBJECT_CODE")
        self.assertEqual(col_map["TOTAL"], "TOTALMARKS")
        self.assertEqual(col_map["GP"], "GRADE_POINTS")
        self.assertEqual(col_map["CR"], "CREDITS")

    def test_full_analysis_reference_file(self):
        """Test full analysis results for PT-series reference workbook."""
        res = analyze_asra_results(self.ref_file)

        # KPI validations
        kpi = res["kpi"]
        self.assertEqual(kpi["total_students"], 12)
        self.assertEqual(kpi["passed_students"], 4)
        self.assertEqual(kpi["failed_students"], 8)
        self.assertAlmostEqual(kpi["pass_pct"], 33.3, places=1)
        self.assertAlmostEqual(kpi["fail_pct"], 66.7, places=1)
        self.assertGreaterEqual(kpi["avg_sgpa"], 6.0)

        # Cohort detection
        cohorts = kpi["available_cohorts"]
        self.assertIn("21PT", cohorts)
        self.assertIn("23PT", cohorts)
        self.assertIn("24PT", cohorts)

        # Specific student verification
        students_by_htno = {s["HTNO"]: s for s in res["complete_students"]}
        
        # 24PT5A6603 (Passed, 9 subjects, total marks 657, SGPA 7.45)
        st_24pt = students_by_htno["24PT5A6603"]
        self.assertTrue(st_24pt["is_passed"])
        self.assertEqual(st_24pt["total_marks"], 657.0)
        self.assertAlmostEqual(st_24pt["sgpa"], 7.45, places=2)

        # 23PT1A6605 (Passed, 8 subjects, total marks 630, SGPA 8.47 / 8.48)
        st_23pt = students_by_htno["23PT1A6605"]
        self.assertTrue(st_23pt["is_passed"])
        self.assertEqual(st_23pt["total_marks"], 630.0)
        self.assertAlmostEqual(st_23pt["sgpa"], 8.47, delta=0.02)

        # 21PT1A6604 (Failed 1 subject: 186DJ)
        st_21pt = students_by_htno["21PT1A6604"]
        self.assertFalse(st_21pt["is_passed"])
        self.assertEqual(st_21pt["failed_count"], 1)

        # Verify Topper Rankings
        top_marks = res["toppers_marks"]["top3"]
        self.assertEqual(len(top_marks), 3)
        self.assertEqual(top_marks[0]["HTNO"], "24PT5A6603")
        self.assertEqual(top_marks[1]["HTNO"], "23PT1A6605")

        top_sgpa = res["toppers_sgpa"]["top3"]
        self.assertEqual(len(top_sgpa), 3)
        self.assertEqual(top_sgpa[0]["HTNO"], "23PT1A6605")
        self.assertEqual(top_sgpa[1]["HTNO"], "24PT5A6603")

        # Subject Analytics
        self.assertEqual(len(res["subjects"]), 9)
        sub_codes = [s["code"] for s in res["subjects"]]
        self.assertIn("18621", sub_codes)
        self.assertIn("18663", sub_codes)

    def test_cohort_filtering(self):
        """Test optional cohort filtering."""
        res_23pt = analyze_asra_results(self.ref_file, selected_cohort="23PT")
        self.assertEqual(res_23pt["kpi"]["total_students"], 8)
        self.assertEqual(res_23pt["kpi"]["passed_students"], 3)
        self.assertEqual(res_23pt["kpi"]["failed_students"], 5)

    def test_pdf_generation(self):
        """Test generating landscape PDF report and file creation."""
        res = analyze_asra_results(self.ref_file)
        out_pdf = os.path.join("uploads", "test_report_run.pdf")
        if os.path.exists(out_pdf):
            os.remove(out_pdf)

        pdf_path = generate_asra_pdf(res, out_pdf)
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(pdf_path), 10000)

        # Clean up test output
        if os.path.exists(out_pdf):
            os.remove(out_pdf)

    def test_text_sanitization(self):
        """Test sanitization function for PDF safety."""
        raw = "📈 Improved! 🎉 Top Topper 🏆 — Grade: 'A+' ✅"
        cleaned = sanitize_text(raw)
        self.assertNotIn("📈", cleaned)
        self.assertNotIn("🎉", cleaned)
        self.assertNotIn("🏆", cleaned)
        self.assertIn("Improved!", cleaned)

    def test_routes_health(self):
        """Regression test: /health endpoint returns 200 OK with status: ok."""
        res = self.app.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {"status": "ok"})

    def test_routes_single_and_compare(self):
        """Regression test: / (AVIH page) and /compare GET endpoints return 200 OK."""
        res1 = self.app.get("/")
        self.assertEqual(res1.status_code, 200)
        self.assertIn(b"AVIH RESULTS ANALYZER", res1.data)
        self.assertIn(b"/asra", res1.data)

        res2 = self.app.get("/compare")
        self.assertEqual(res2.status_code, 200)
        self.assertIn(b"Compare Semesters", res2.data)
        self.assertIn(b"/asra", res2.data)

    def test_route_asra_get(self):
        """Test /asra GET renders the dedicated ASRA upload form with 3 nav buttons."""
        res = self.app.get("/asra")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"ASRA RESULTS ANALYZER", res.data)
        self.assertIn(b"Upload PT-Series Excel Markslist", res.data)
        self.assertIn(b"AVIH", res.data)
        self.assertIn(b"ASRA", res.data)
        self.assertIn(b"Compare Semesters", res.data)

    def test_navigation_between_avih_and_asra(self):
        """Test that first page (/) is AVIH and /asra is ASRA."""
        res_avih = self.app.get("/")
        self.assertEqual(res_avih.status_code, 200)
        self.assertIn(b"AVIH RESULTS ANALYZER", res_avih.data)
        self.assertIn(b"Q6-Series JNTUH Examination Result Analysis", res_avih.data)

        res_asra = self.app.get("/asra")
        self.assertEqual(res_asra.status_code, 200)
        self.assertIn(b"ASRA RESULTS ANALYZER", res_asra.data)
        self.assertIn(b"PT-Series JNTUH Examination Result Analysis", res_asra.data)

    def test_failed_subjects_names_and_counts(self):
        """Test that failed students include failed subject names, codes, and counts."""
        res = analyze_asra_results(self.ref_file)
        failed_students = res["failed_students"]
        self.assertEqual(len(failed_students), 8)

        # Student 21PT1A6604 failed 1 subject
        st1 = next(s for s in failed_students if s["HTNO"] == "21PT1A6604")
        self.assertEqual(st1["failed_count"], 1)
        self.assertEqual(len(st1["failed_subjects"]), 1)
        self.assertEqual(st1["failed_subjects"][0]["code"], "186DJ")
        self.assertEqual(st1["failed_subjects"][0]["name"], "NATURAL LANGUAGE PROCESSING")
        self.assertEqual(st1["failed_subjects"][0]["grade"], "F")

        # Student 23PT1A6601 failed 3 subjects
        st2 = next(s for s in failed_students if s["HTNO"] == "23PT1A6601")
        self.assertEqual(st2["failed_count"], 3)
        self.assertEqual(len(st2["failed_subjects"]), 3)
        sub_names = [s["name"] for s in st2["failed_subjects"]]
        self.assertIn("KNOWLEDGE REPRESENTATION AND REASONING", sub_names)
        self.assertIn("NATURAL LANGUAGE PROCESSING", sub_names)
        self.assertIn("FUNDAMENTALS OF INTERNET OF THINGS", sub_names)

    def test_route_asra_post_and_download(self):
        """Integration test: upload file to /asra and verify response, clean failed subjects HTML & PDF download."""
        with open(self.ref_file, "rb") as fp:
            data = {
                "file": (BytesIO(fp.read()), "PT-66-III B.Tech. II Semester (R22) Regular(3).xlsx"),
                "college": "ASRA"
            }
            res = self.app.post("/asra", data=data, content_type="multipart/form-data")
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"Outstanding Achievements", res.data)
            self.assertIn(b"24PT5A6603", res.data)
            self.assertIn(b"23PT1A6605", res.data)
            
            # Verify failed candidates breakdown:
            self.assertIn(b"Failed Candidates Breakdown", res.data)
            failed_section = res.data.split(b"Failed Candidates Breakdown")[1].split(b"Calculation Methodology")[0]
            # Displays failed subject name and numbering
            self.assertIn(b"NATURAL LANGUAGE PROCESSING", failed_section)
            # Verify NO subject code (186DJ) and NO grade (Grade:) in the failed subjects table section
            self.assertNotIn(b"186DJ", failed_section)
            self.assertNotIn(b"Grade:", failed_section)

        # Test /download-asra
        dl_res = self.app.get("/download-asra")
        self.assertEqual(dl_res.status_code, 200)
        self.assertEqual(dl_res.headers.get("Content-Type"), "application/pdf")
        self.assertIn(b"%PDF", dl_res.data[:10])

    def test_avih_workbook_analysis_and_pdf(self):
        """Test analyzing an AVIH (Q6 series) workbook and generating AVIH PDF."""
        avih_file = os.path.join("uploads", "Q6-66-III B.Tech. I Semester (R22) Regular.xlsx")
        if os.path.exists(avih_file):
            res_avih = analyze_asra_results(avih_file, college="AVIH")
            self.assertEqual(res_avih["kpi"]["college"], "AVIH")
            self.assertEqual(res_avih["kpi"]["total_students"], 43)
            self.assertEqual(res_avih["kpi"]["passed_students"], 22)
            self.assertEqual(res_avih["kpi"]["failed_students"], 21)

            # Test PDF generation
            out_pdf = os.path.join("uploads", "test_avih_report.pdf")
            pdf_path = generate_asra_pdf(res_avih, out_pdf)
            self.assertTrue(os.path.exists(pdf_path))
            if os.path.exists(out_pdf):
                os.remove(out_pdf)


if __name__ == "__main__":
    unittest.main()
