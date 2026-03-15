"""
train_model.py (Optimized)
--------------------------
Trains two models:
  1. cgpa_model.pkl    — SGPA trend predictor (Ridge Regression)
  2. prereq_model.pkl  — Grade predictor from prerequisites (Random Forest)

Optimizations:
  - Single bulk DB query instead of N+1 queries (173K → 3 queries)
  - Better feature engineering for SGPA model
  - Balanced class weights for Random Forest
  - Normal distribution for synthetic CGPA (more realistic)
  - Proper confidence normalization

Usage:
    python train_model.py

Requirements:
    - pip install scikit-learn joblib numpy
"""

import random
import numpy as np
from db import execute_query
from ml.predictor import train_sgpa_model, train_prereq_model

random.seed(42)
np.random.seed(42)

# ─────────────────────────────────────────────────────────────
# MODEL 1: SGPA Predictor
# ─────────────────────────────────────────────────────────────

def build_sgpa_training_data():
    print("[1/2] Building SGPA training data from DB...")

    # Single query — fetch all completed semester SGPAs at once
    rows = execute_query("""
        SELECT student_id, semester_id, sgpa
        FROM Student_Semester_Status
        WHERE status = 'Completed'
          AND sgpa IS NOT NULL
        ORDER BY student_id, semester_id
    """) or []

    # Group by student
    student_sgpas = {}
    for r in rows:
        sid = r['student_id']
        if sid not in student_sgpas:
            student_sgpas[sid] = []
        student_sgpas[sid].append(float(r['sgpa']))

    all_data = [v for v in student_sgpas.values() if len(v) >= 2]
    print(f"    → {len(all_data)} students with 2+ semesters of data")
    return all_data


# ─────────────────────────────────────────────────────────────
# MODEL 2: Prerequisite Grade Predictor
# ─────────────────────────────────────────────────────────────

GRADE_POINTS = {'O':10,'A':9,'B':8,'C':7,'D':6,'F':0}
DIFFICULTY   = ['Easy','Medium','Hard']

def generate_synthetic_prereq_data(n=15000):
    """
    Generate synthetic training data with realistic CGPA distribution.
    Uses normal distribution centered at 7.5 (realistic student average).
    """
    rows = []

    for _ in range(n):
        n_prereqs  = random.randint(1, 3)
        prereq_pts = [random.choice(list(GRADE_POINTS.values()))
                      for _ in range(n_prereqs)]
        avg  = sum(prereq_pts) / len(prereq_pts)
        diff = random.choice(DIFFICULTY)

        # Realistic CGPA: normal distribution centered at 7.5
        cgpa = round(np.clip(np.random.normal(7.5, 1.2), 5.0, 10.0), 2)

        diff_pen = {'Easy': 0, 'Medium': 0.8, 'Hard': 1.6}[diff]
        score    = (avg * 0.55 + cgpa * 0.45) - diff_pen
        score    = float(np.clip(score + np.random.normal(0, 0.6), 0.0, 10.0))

        if   score >= 9.2: outcome = random.choices(['O','A'],         [70,30])[0]
        elif score >= 8.0: outcome = random.choices(['O','A','B'],     [15,55,30])[0]
        elif score >= 7.0: outcome = random.choices(['A','B','C'],     [10,55,35])[0]
        elif score >= 6.0: outcome = random.choices(['B','C','D'],     [15,50,35])[0]
        elif score >= 5.0: outcome = random.choices(['C','D','F'],     [20,50,30])[0]
        else:              outcome = random.choices(['D','F'],         [30,70])[0]

        rows.append({
            'prereq_points': prereq_pts,
            'difficulty':    diff,
            'cgpa':          cgpa,
            'outcome_grade': outcome
        })

    return rows


def build_prereq_training_data_from_db():
    """
    Optimized: Fetches ALL data in 3 bulk queries instead of 173K queries.
    """
    print("    → Extracting real student prerequisite patterns from DB...")

    # ── Query 1: All prerequisite pairs ──────────────────────
    prereq_pairs = execute_query("""
        SELECT subject_id, prereq_id, weight
        FROM Subject_Prerequisites
    """) or []

    # Group prereqs by target subject
    subject_prereqs = {}
    for p in prereq_pairs:
        sid = p['subject_id']
        if sid not in subject_prereqs:
            subject_prereqs[sid] = []
        subject_prereqs[sid].append({
            'prereq_id': p['prereq_id'],
            'weight':    float(p['weight'])
        })

    # ── Query 2: All student grades in one shot ───────────────
    all_grades_rows = execute_query("""
        SELECT g.student_id, g.subject_id, gp.points
        FROM Grades g
        JOIN GradePoints gp ON g.grade = gp.grade
    """) or []

    # Build grade lookup: {student_id: {subject_id: points}}
    grade_lookup = {}
    for r in all_grades_rows:
        sid  = r['student_id']
        subj = r['subject_id']
        pts  = float(r['points'])
        if sid not in grade_lookup:
            grade_lookup[sid] = {}
        grade_lookup[sid][subj] = pts

    # ── Query 3: All student CGPAs in one shot ────────────────
    cgpa_rows = execute_query("""
        SELECT g.student_id,
               ROUND(
                   SUM(CASE WHEN g.grade != 'F' AND s.credits > 0
                            THEN s.credits * gp.points ELSE 0 END)
                   / NULLIF(SUM(CASE WHEN g.grade != 'F' AND s.credits > 0
                                    THEN s.credits ELSE 0 END), 0)
               , 2) AS cgpa
        FROM Grades g
        JOIN Subjects s     ON g.subject_id = s.subject_id
        JOIN GradePoints gp ON g.grade      = gp.grade
        GROUP BY g.student_id
    """) or []

    cgpa_lookup = {r['student_id']: float(r['cgpa']) if r['cgpa'] else 7.0
                   for r in cgpa_rows}

    # ── Query 4: Subject difficulties ────────────────────────
    diff_rows = execute_query("""
        SELECT subject_id, difficulty FROM Subjects
    """) or []
    diff_lookup = {r['subject_id']: r['difficulty'] for r in diff_rows}

    # ── Process in Python ─────────────────────────────────────
    rows = []
    students = list(grade_lookup.keys())

    for student_id in students:
        student_grades = grade_lookup.get(student_id, {})
        cgpa           = cgpa_lookup.get(student_id, 7.0)

        for target_sub_id, prereqs in subject_prereqs.items():
            # Student must have a grade for this target subject
            if target_sub_id not in student_grades:
                continue

            outcome_pts = student_grades[target_sub_id]
            # Convert points back to grade
            pts_to_grade = {10:'O',9:'A',8:'B',7:'C',6:'D',0:'F'}
            outcome_grade = pts_to_grade.get(int(outcome_pts), 'C')
            difficulty    = diff_lookup.get(target_sub_id, 'Medium')

            # Get prereq grades
            prereq_pts = []
            for p in prereqs:
                if p['prereq_id'] in student_grades:
                    prereq_pts.append(
                        student_grades[p['prereq_id']] * p['weight']
                    )

            if prereq_pts:
                rows.append({
                    'prereq_points': prereq_pts,
                    'difficulty':    difficulty,
                    'cgpa':          cgpa,
                    'outcome_grade': outcome_grade
                })

    print(f"    → {len(rows)} real prerequisite training samples from DB")
    return rows


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("=" * 55)
    print("AcadTrack — Model Training (Optimized)")
    print("=" * 55)

    # ── Model 1: SGPA ──────────────────────────────────────
    sgpa_data = build_sgpa_training_data()
    if sgpa_data:
        train_sgpa_model(sgpa_data)
        print("    ✓ cgpa_model.pkl saved\n")
    else:
        print("    ✗ Not enough SGPA data — skipping SGPA model\n")

    # ── Model 2: Prereq Grade Predictor ────────────────────
    print("[2/2] Building prerequisite grade prediction training data...")
    synthetic = generate_synthetic_prereq_data(n=15000)
    print(f"    → {len(synthetic)} synthetic samples generated")

    real     = build_prereq_training_data_from_db()
    combined = synthetic + real
    random.shuffle(combined)

    print(f"    → {len(combined)} total training samples")
    train_prereq_model(combined)
    print("    ✓ prereq_model.pkl saved\n")

    print("=" * 55)
    print("Training complete. Both models are ready.")
    print("Run: python app.py")
    print("=" * 55)