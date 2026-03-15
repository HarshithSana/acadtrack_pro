from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from db import execute_query
from ml.predictor import predict_next_sgpa, get_trend, predict_prereq_grade
from functools import wraps
import math

app = Flask(__name__)
app.secret_key = 'acadtrack_secret_2024'

# ═══════════════════════════════════════════════════════════════
# AUTH DECORATORS
# ═══════════════════════════════════════════════════════════════

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'student_id' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Admin access required.', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# ═══════════════════════════════════════════════════════════════
# ACADEMIC HELPERS
# ═══════════════════════════════════════════════════════════════

def get_sgpa(student_id, semester_id, department):
    """SGPA for one semester — uses Branch_Subjects to filter dept subjects only."""
    rows = execute_query("""
        SELECT s.credits, gp.points
        FROM Grades g
        JOIN Subjects s         ON g.subject_id  = s.subject_id
        JOIN Branch_Subjects bs ON bs.subject_id = s.subject_id
                                AND bs.department = %s
                                AND bs.semester   = g.semester_id
        JOIN GradePoints gp     ON g.grade = gp.grade
        WHERE g.student_id  = %s
          AND g.semester_id = %s
          AND g.grade  != 'F'
          AND s.credits > 0
    """, (department, student_id, semester_id))
    if not rows:
        return 0.0
    tp = sum(float(r['credits']) * float(r['points']) for r in rows)
    tc = sum(float(r['credits']) for r in rows)
    return round(tp / tc, 2) if tc else 0.0

def get_cgpa(student_id, department):
    """CGPA across all semesters — uses Branch_Subjects to filter dept subjects only."""
    rows = execute_query("""
        SELECT s.credits, gp.points
        FROM Grades g
        JOIN Subjects s         ON g.subject_id  = s.subject_id
        JOIN Branch_Subjects bs ON bs.subject_id = s.subject_id
                                AND bs.department = %s
                                AND bs.semester   = g.semester_id
        JOIN GradePoints gp     ON g.grade = gp.grade
        WHERE g.student_id = %s
          AND g.grade != 'F'
          AND s.credits > 0
    """, (department, student_id))
    if not rows:
        return 0.0
    tp = sum(float(r['credits']) * float(r['points']) for r in rows)
    tc = sum(float(r['credits']) for r in rows)
    return round(tp / tc, 2) if tc else 0.0

def get_backlogs(student_id, department):
    """Active backlogs — F grades not yet cleared via backlog_attempts."""
    return execute_query("""
        SELECT s.subject_name,
               g.semester_id AS semester_number,
               g.marks,
               g.grade
        FROM Grades g
        JOIN Subjects s ON g.subject_id = s.subject_id
        WHERE g.student_id = %s
          AND g.grade = 'F'
          AND g.subject_id NOT IN (
              SELECT DISTINCT subject_id
              FROM Backlog_Attempts
              WHERE student_id = %s
                AND status = 'Cleared'
          )
        ORDER BY g.semester_id, s.subject_name
    """, (student_id, student_id)) or []

def get_backlog_history(student_id):
    """
    Full backlog attempt history for a student — all attempts including cleared.
    Visible to both student (dashboard) and admin (profile).
    Returns grouped by subject with full attempt chain.
    """
    rows = execute_query("""
        SELECT
            s.subject_name,
            s.subject_id,
            ba.attempt_number,
            ba.attempt_semester,
            ba.attempt_date,
            ba.marks,
            ba.grade,
            ba.status,
            ba.cleared_semester
        FROM Backlog_Attempts ba
        JOIN Subjects s ON ba.subject_id = s.subject_id
        WHERE ba.student_id = %s
        ORDER BY ba.subject_id, ba.attempt_number
    """, (student_id,)) or []

    # Group by subject
    history = {}
    for r in rows:
        sid = r['subject_id']
        if sid not in history:
            history[sid] = {
                'subject_name':    r['subject_name'],
                'attempts':        [],
                'status':          'Active',
                'cleared_semester': None
            }
        history[sid]['attempts'].append({
            'attempt_number':  r['attempt_number'],
            'attempt_semester': r['attempt_semester'],
            'attempt_date':    r['attempt_date'],
            'marks':           r['marks'],
            'grade':           r['grade'],
            'status':          r['status']
        })
        if r['status'] == 'Cleared':
            history[sid]['status']           = 'Cleared'
            history[sid]['cleared_semester'] = r['cleared_semester']

    return list(history.values())

def get_semester_data(student_id, department):
    """All completed semesters with SGPA — reads from Student_Semester_Status."""
    rows = execute_query("""
        SELECT sss.semester_id, sss.semester_id AS semester_number,
               sss.sgpa, sss.status, sss.completion_date
        FROM Student_Semester_Status sss
        WHERE sss.student_id = %s
          AND sss.status = 'Completed'
        ORDER BY sss.semester_id
    """, (student_id,)) or []

    # Fallback: compute from Grades if Student_Semester_Status empty
    if not rows:
        sems = execute_query("""
            SELECT DISTINCT g.semester_id, g.semester_id AS semester_number
            FROM Grades g
            JOIN Branch_Subjects bs ON bs.subject_id  = g.subject_id
                                    AND bs.department = %s
                                    AND bs.semester   = g.semester_id
            WHERE g.student_id = %s
            ORDER BY g.semester_id
        """, (department, student_id)) or []
        result = []
        for sem in sems:
            sgpa = get_sgpa(student_id, sem['semester_id'], department)
            result.append({
                'semester_id':     sem['semester_id'],
                'semester_number': sem['semester_number'],
                'sgpa':            sgpa
            })
        return result

    return [dict(r) for r in rows]

def get_dept_rank(student_id, department):
    """Rank within department — single SQL, no loop."""
    rows = execute_query("""
        SELECT
            st.student_id,
            ROUND(
                SUM(CASE WHEN g.grade != 'F' AND s.credits > 0
                         THEN s.credits * gp.points ELSE 0 END)
                /
                NULLIF(SUM(CASE WHEN g.grade != 'F' AND s.credits > 0
                               THEN s.credits ELSE 0 END), 0)
            , 2) AS cgpa
        FROM Students st
        LEFT JOIN Grades g           ON st.student_id  = g.student_id
        LEFT JOIN Subjects s         ON g.subject_id   = s.subject_id
        LEFT JOIN Branch_Subjects bs ON bs.subject_id  = s.subject_id
                                    AND bs.department  = st.department
                                    AND bs.semester    = g.semester_id
        LEFT JOIN GradePoints gp     ON g.grade        = gp.grade
        WHERE st.department = %s
        GROUP BY st.student_id
        ORDER BY cgpa DESC
    """, (department,)) or []

    total = len(rows)
    for i, row in enumerate(rows, 1):
        if row['student_id'] == student_id:
            return i, total
    return None, total

def get_year_sem_label(current_semester):
    """
    Returns year-semester label like '3-2' from semester number.
    Sem 1→1-1, Sem 2→1-2, Sem 3→2-1, Sem 4→2-2 ... Sem 6→3-2
    """
    year        = math.ceil(current_semester / 2)
    sem_in_year = 2 if current_semester % 2 == 0 else 1
    return f"{year}-{sem_in_year}"

def get_credits_summary(student_id, department):
    """Returns (credits_earned, total_credits) for the student."""
    row = execute_query("""
        SELECT credits_earned, total_credits
        FROM Students
        WHERE student_id = %s
    """, (student_id,))
    if row:
        return float(row[0]['credits_earned']), float(row[0]['total_credits'])
    return 0.0, 0.0

def update_student_flags(student_id, department, sgpa_history):
    """
    Recomputes and saves risk_flag and trend based on latest performance.
    Called after any grade change.
    """
    trend     = get_trend(sgpa_history)
    backlogs  = get_backlogs(student_id, department)
    cgpa      = get_cgpa(student_id, department)
    n_backlogs = len(backlogs)

    # Risk: HIGH if >3 active backlogs or CGPA <5.5
    # MEDIUM if 1-3 backlogs or CGPA 5.5–6.5
    # LOW otherwise
    if n_backlogs > 3 or cgpa < 5.5:
        risk = 'HIGH'
    elif n_backlogs > 0 or cgpa < 6.5:
        risk = 'MEDIUM'
    else:
        risk = 'LOW'

    # Map trend string to DB enum
    trend_map = {
        'Improving': 'Improving',
        'Declining': 'Declining',
        'Stable':    'Stable',
        'At Risk':   'At Risk'
    }
    db_trend = trend_map.get(trend, 'Stable')

    execute_query("""
        UPDATE Students SET risk_flag = %s, trend = %s
        WHERE student_id = %s
    """, (risk, db_trend, student_id), fetch=False)

# ═══════════════════════════════════════════════════════════════
# STUDENT ROUTES
# ═══════════════════════════════════════════════════════════════

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        sid = request.form.get('student_id', '').strip()
        pwd = request.form.get('password', '').strip()
        student = execute_query(
            "SELECT * FROM Students WHERE student_id = %s AND password = %s",
            (sid, pwd)
        )
        if student:
            s = student[0]
            session['student_id']       = s['student_id']
            session['student_name']     = s['name']
            session['department']       = s['department']
            session['email']            = s.get('email', '')
            session['current_semester'] = s.get('current_semester', 1)
            return redirect(url_for('dashboard'))
        flash('Invalid Roll Number or Password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    sid          = session['student_id']
    dept         = session['department']
    current_sem  = session.get('current_semester', 6)

    cgpa             = get_cgpa(sid, dept)
    backlogs         = get_backlogs(sid, dept)
    backlog_history  = get_backlog_history(sid)
    semester_data    = get_semester_data(sid, dept)
    sgpa_history     = [float(s['sgpa']) for s in semester_data if s.get('sgpa')]
    dept_rank, dept_total = get_dept_rank(sid, dept)
    credits_earned, total_credits = get_credits_summary(sid, dept)
    year_sem_label   = get_year_sem_label(current_sem)

    prediction = None
    trend      = get_trend(sgpa_history)
    if len(sgpa_history) >= 2:
        prediction = predict_next_sgpa(sgpa_history)

    all_grades = execute_query("""
        SELECT g.grade, g.marks, s.subject_name, s.credits,
               g.semester_id AS semester_number, gp.points
        FROM Grades g
        JOIN Subjects s     ON g.subject_id = s.subject_id
        JOIN GradePoints gp ON g.grade      = gp.grade
        WHERE g.student_id = %s
        ORDER BY g.semester_id, s.subject_name
    """, (sid,)) or []

    # Fetch student risk_flag and trend from DB (updated by admin/grade changes)
    student_row = execute_query(
        "SELECT risk_flag, trend FROM Students WHERE student_id = %s", (sid,)
    )
    risk_flag  = student_row[0]['risk_flag']  if student_row else 'LOW'
    db_trend   = student_row[0]['trend']      if student_row else 'Stable'

    chart_sems     = [f"Sem {s['semester_number']}" for s in semester_data]
    chart_sgpas    = sgpa_history
    chart_subjects = [g['subject_name'][:16] for g in all_grades]
    chart_marks    = [g['marks'] for g in all_grades]

    # Convert date objects to strings for JSON serialization
    for g in all_grades:
        if hasattr(g.get('recorded_date', ''), 'isoformat'):
            g['recorded_date'] = g['recorded_date'].isoformat()

    return render_template('dashboard.html',
        student_name    = session['student_name'],
        student_id      = sid,
        department      = dept,
        email           = session.get('email', ''),
        cgpa            = cgpa,
        backlogs        = backlogs,
        backlog_history = backlog_history,
        semester_data   = semester_data,
        all_grades      = all_grades,
        dept_rank       = dept_rank,
        dept_total      = dept_total,
        prediction      = prediction,
        trend           = trend,
        risk_flag       = risk_flag,
        db_trend        = db_trend,
        credits_earned  = credits_earned,
        total_credits   = total_credits,
        year_sem_label  = year_sem_label,
        current_semester= current_sem,
        chart_sems      = chart_sems,
        chart_sgpas     = chart_sgpas,
        chart_subjects  = chart_subjects,
        chart_marks     = chart_marks
    )

@app.route('/semester/<int:sem_number>')
@login_required
def semester_report(sem_number):
    sid  = session['student_id']
    dept = session['department']

    grades = execute_query("""
        SELECT g.grade, g.marks, s.subject_name, s.credits,
               gp.points,
               CASE WHEN g.grade = 'F' OR s.credits = 0 THEN 0
                    ELSE (s.credits * gp.points) END AS grade_points
        FROM Grades g
        JOIN Subjects s         ON g.subject_id  = s.subject_id
        JOIN Branch_Subjects bs ON bs.subject_id = s.subject_id
                                AND bs.department = %s
                                AND bs.semester   = g.semester_id
        JOIN GradePoints gp     ON g.grade = gp.grade
        WHERE g.student_id  = %s
          AND g.semester_id = %s
        ORDER BY s.subject_name
    """, (dept, sid, sem_number)) or []

    if not grades:
        flash(f'No data found for Semester {sem_number}.', 'error')
        return redirect(url_for('dashboard'))

    sgpa     = get_sgpa(sid, sem_number, dept)
    backlogs = [g for g in grades if g['grade'] == 'F']

    earned_credits = sum(
        float(g['credits']) for g in grades
        if g['grade'] != 'F' and float(g['credits']) > 0
    )
    max_credits = sum(float(g['credits']) for g in grades if float(g['credits']) > 0)

    # Backlog attempt history for subjects in this semester
    backlog_history = execute_query("""
        SELECT
            s.subject_name, ba.attempt_number,
            ba.attempt_semester, ba.attempt_date,
            ba.marks, ba.grade, ba.status, ba.cleared_semester
        FROM Backlog_Attempts ba
        JOIN Subjects s ON ba.subject_id = s.subject_id
        WHERE ba.student_id     = %s
          AND ba.attempt_semester = %s
        ORDER BY ba.subject_id, ba.attempt_number
    """, (sid, sem_number)) or []

    return render_template('semester_report.html',
        student_name    = session['student_name'],
        department      = dept,
        student_id      = sid,
        sem_number      = sem_number,
        grades          = grades,
        sgpa            = sgpa,
        earned_credits  = earned_credits,
        max_credits     = max_credits,
        backlogs        = backlogs,
        backlog_history = backlog_history
    )

# ═══════════════════════════════════════════════════════════════
# ADMIN ROUTES
# ═══════════════════════════════════════════════════════════════

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        admin = execute_query(
            "SELECT * FROM Admins WHERE username = %s AND password = %s",
            (username, password)
        )
        if admin:
            session['admin_id']   = admin[0]['admin_id']
            session['admin_name'] = admin[0]['username']
            return redirect(url_for('admin_panel'))
        flash('Invalid credentials.', 'error')
    return render_template('admin/admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

@app.route('/admin')
@admin_required
def admin_panel():
    total_students = execute_query("SELECT COUNT(*) as c FROM Students")[0]['c']
    total_subjects = execute_query("SELECT COUNT(*) as c FROM Subjects")[0]['c']
    total_grades   = execute_query("SELECT COUNT(*) as c FROM Grades")[0]['c']

    dept_stats = execute_query("""
        SELECT s.department,
               COUNT(DISTINCT s.student_id) AS cnt,
               SUM(CASE WHEN ba.status = 'Failed' THEN 1 ELSE 0 END) AS active_backlogs,
               COUNT(DISTINCT CASE WHEN s.risk_flag = 'HIGH' THEN s.student_id END) AS high_risk
        FROM Students s
        LEFT JOIN Backlog_Attempts ba ON s.student_id = ba.student_id
                                     AND ba.status = 'Failed'
        GROUP BY s.department
        ORDER BY s.department
    """) or []

    # Backlog clearance rate — cleared / total attempts
    clearance = execute_query("""
        SELECT
            COUNT(CASE WHEN status = 'Cleared' THEN 1 END) AS cleared,
            COUNT(*) AS total
        FROM Backlog_Attempts
        WHERE attempt_number > 1
    """)
    clearance_rate = 0
    if clearance and clearance[0]['total']:
        clearance_rate = round(
            (clearance[0]['cleared'] / clearance[0]['total']) * 100, 1
        )

    active_backlogs = execute_query(
        "SELECT COUNT(*) as c FROM Backlog_Attempts WHERE status = 'Failed'"
    )[0]['c']

    return render_template('admin/admin_panel.html',
        admin_name      = session['admin_name'],
        total_students  = total_students,
        total_subjects  = total_subjects,
        total_grades    = total_grades,
        dept_stats      = dept_stats,
        active_backlogs = active_backlogs,
        clearance_rate  = clearance_rate
    )

@app.route('/admin/students')
@admin_required
def manage_students():
    dept_filter = request.args.get('department', '')
    if dept_filter:
        students = execute_query(
            "SELECT * FROM Students WHERE department = %s ORDER BY name",
            (dept_filter,)
        ) or []
    else:
        students = execute_query(
            "SELECT * FROM Students ORDER BY department, name"
        ) or []

    # Attach year-sem label to each student
    for s in students:
        s['year_sem'] = get_year_sem_label(s.get('current_semester', 1))

    departments = ['CSE', 'IT', 'CSM', 'CSD']
    return render_template('admin/manage_students.html',
        students    = students,
        departments = departments,
        dept_filter = dept_filter,
        admin_name  = session['admin_name']
    )

@app.route('/admin/students/add', methods=['POST'])
@admin_required
def add_student():
    execute_query(
        """INSERT INTO Students
           (student_id, name, email, password, department, current_semester)
           VALUES (%s,%s,%s,%s,%s,%s)""",
        (request.form['student_id'], request.form['name'], request.form['email'],
         request.form['password'], request.form['department'],
         request.form.get('current_semester', 1)),
        fetch=False
    )
    flash(f"Student {request.form['name']} added successfully.", 'success')
    return redirect(url_for('manage_students'))

@app.route('/admin/students/delete/<sid>')
@admin_required
def delete_student(sid):
    execute_query("DELETE FROM Students WHERE student_id = %s", (sid,), fetch=False)
    flash('Student deleted.', 'success')
    return redirect(url_for('manage_students'))

@app.route('/admin/grades')
@admin_required
def manage_grades():
    dept_filter = request.args.get('department', '')
    if dept_filter:
        grades = execute_query("""
            SELECT g.grade_id, g.student_id, st.name, st.department,
                   s.subject_name, g.semester_id AS semester_number,
                   g.marks, g.grade, g.recorded_date
            FROM Grades g
            JOIN Students st ON g.student_id = st.student_id
            JOIN Subjects s  ON g.subject_id = s.subject_id
            WHERE st.department = %s
            AND g.grade IS NOT NULL
            GROUP BY g.grade_id, g.student_id, st.name, st.department,
                     s.subject_name, g.semester_id, g.marks, g.grade, g.recorded_date
            ORDER BY g.semester_id, st.name
        """, (dept_filter,)) or []
    else:
        grades = execute_query("""
            SELECT g.grade_id, g.student_id, st.name, st.department,
                   s.subject_name, g.semester_id AS semester_number,
                   g.marks, g.grade, g.recorded_date
            FROM Grades g
            JOIN Students st ON g.student_id = st.student_id
            JOIN Subjects s  ON g.subject_id = s.subject_id
            WHERE g.grade IS NOT NULL
            GROUP BY g.grade_id, g.student_id, st.name, st.department,
                     s.subject_name, g.semester_id, g.marks, g.grade, g.recorded_date
            ORDER BY g.semester_id, st.name
            LIMIT 200
        """) or []

    students    = execute_query("SELECT student_id, name, department FROM Students ORDER BY department, name") or []
    subjects    = execute_query("""
        SELECT DISTINCT s.subject_id, s.subject_name, s.credits, bs.department, bs.semester
        FROM Subjects s
        JOIN Branch_Subjects bs ON bs.subject_id = s.subject_id
        ORDER BY bs.department, bs.semester, s.subject_name
    """) or []
    semesters   = execute_query("SELECT * FROM Semesters ORDER BY semester_number") or []
    gpoints     = execute_query("SELECT grade FROM GradePoints ORDER BY points DESC") or []
    departments = ['CSE', 'IT', 'CSM', 'CSD']

    return render_template('admin/manage_grades.html',
        grades       = grades,
        students     = students,
        subjects     = subjects,
        semesters    = semesters,
        grade_points = gpoints,
        departments  = departments,
        dept_filter  = dept_filter,
        admin_name   = session['admin_name']
    )

@app.route('/admin/grades/add', methods=['POST'])
@admin_required
def add_grade():
    from datetime import date
    sid        = request.form['student_id']
    subject_id = request.form['subject_id']
    sem_id     = request.form['semester_id']
    marks      = int(request.form['marks'])
    grade      = request.form['grade']
    rec_date   = date.today().isoformat()

    execute_query(
        """INSERT INTO Grades (student_id, subject_id, semester_id, marks, grade, recorded_date)
           VALUES (%s,%s,%s,%s,%s,%s)
           ON DUPLICATE KEY UPDATE marks=%s, grade=%s, recorded_date=%s""",
        (sid, subject_id, sem_id, marks, grade, rec_date, marks, grade, rec_date),
        fetch=False
    )

    # If grade is F — record in Backlog_Attempts
    if grade == 'F':
        # Find attempt number for this student + subject
        existing = execute_query("""
            SELECT MAX(attempt_number) AS max_att
            FROM Backlog_Attempts
            WHERE student_id = %s AND subject_id = %s
        """, (sid, subject_id))
        attempt_num = (existing[0]['max_att'] or 0) + 1

        execute_query("""
            INSERT INTO Backlog_Attempts
            (student_id, subject_id, attempt_number, attempt_semester,
             attempt_date, marks, grade, status, cleared_semester)
            VALUES (%s,%s,%s,%s,%s,%s,'F','Failed',NULL)
        """, (sid, subject_id, attempt_num, sem_id, rec_date, marks), fetch=False)

    else:
        # If passing — check if any prior Failed attempts exist and mark Cleared
        execute_query("""
            UPDATE Backlog_Attempts
            SET status = 'Cleared', cleared_semester = %s
            WHERE student_id = %s AND subject_id = %s AND status = 'Failed'
        """, (sem_id, sid, subject_id), fetch=False)

    # Update risk_flag and trend
    student  = execute_query("SELECT department FROM Students WHERE student_id = %s", (sid,))
    if student:
        dept          = student[0]['department']
        sem_data      = get_semester_data(sid, dept)
        sgpa_history  = [float(s['sgpa']) for s in sem_data if s.get('sgpa')]
        update_student_flags(sid, dept, sgpa_history)

    flash('Grade saved successfully.', 'success')
    return redirect(url_for('manage_grades'))

@app.route('/admin/grades/delete/<int:gid>')
@admin_required
def delete_grade(gid):
    execute_query("DELETE FROM Grades WHERE grade_id = %s", (gid,), fetch=False)
    flash('Grade deleted.', 'success')
    return redirect(url_for('manage_grades'))

@app.route('/admin/rankings')
@admin_required
def admin_rankings():
    cgpa_rows = execute_query("""
        SELECT
            st.student_id, st.name, st.department,
            st.risk_flag, st.trend, st.current_semester,
            ROUND(
                SUM(CASE WHEN g.grade != 'F' AND s.credits > 0
                         THEN s.credits * gp.points ELSE 0 END)
                /
                NULLIF(SUM(CASE WHEN g.grade != 'F' AND s.credits > 0
                               THEN s.credits ELSE 0 END), 0)
            , 2) AS cgpa
        FROM Students st
        LEFT JOIN Grades g           ON st.student_id  = g.student_id
        LEFT JOIN Subjects s         ON g.subject_id   = s.subject_id
        LEFT JOIN Branch_Subjects bs ON bs.subject_id  = s.subject_id
                                    AND bs.department  = st.department
                                    AND bs.semester    = g.semester_id
        LEFT JOIN GradePoints gp     ON g.grade        = gp.grade
        GROUP BY st.student_id, st.name, st.department,
                 st.risk_flag, st.trend, st.current_semester
        ORDER BY st.department, cgpa DESC
    """) or []

    backlog_rows = execute_query("""
        SELECT student_id, COUNT(*) AS backlog_count
        FROM Backlog_Attempts
        WHERE status = 'Failed'
        GROUP BY student_id
    """) or []
    backlog_map = {r['student_id']: r['backlog_count'] for r in backlog_rows}

    dept_rankings = {}
    for r in cgpa_rows:
        dept = r['department']
        if dept not in dept_rankings:
            dept_rankings[dept] = []
        dept_rankings[dept].append({
            'student_id':   r['student_id'],
            'name':         r['name'],
            'cgpa':         float(r['cgpa']) if r['cgpa'] else 0.0,
            'backlogs':     backlog_map.get(r['student_id'], 0),
            'risk_flag':    r['risk_flag'],
            'trend':        r['trend'],
            'year_sem':     get_year_sem_label(r.get('current_semester', 1))
        })

    for dept in dept_rankings:
        for i, entry in enumerate(dept_rankings[dept], 1):
            entry['rank'] = i

    return render_template('admin/rankings.html',
        dept_rankings = dept_rankings,
        admin_name    = session['admin_name']
    )

# ─────────────────────────────────────────────────────────────
# ADMIN — Backlog Tracking View
# ─────────────────────────────────────────────────────────────

@app.route('/admin/backlogs')
@admin_required
def admin_backlogs():
    """Branch-wise view of all active and cleared backlogs with attempt history."""
    dept_filter = request.args.get('department', '')

    query = """
        SELECT
            ba.student_id, st.name, st.department,
            s.subject_name, s.subject_id,
            ba.attempt_number, ba.attempt_semester,
            ba.attempt_date, ba.marks, ba.grade,
            ba.status, ba.cleared_semester
        FROM Backlog_Attempts ba
        JOIN Students st ON ba.student_id = st.student_id
        JOIN Subjects s  ON ba.subject_id  = s.subject_id
    """
    params = []
    if dept_filter:
        query  += " WHERE st.department = %s"
        params  = [dept_filter]
    query += " ORDER BY st.department, ba.student_id, ba.subject_id, ba.attempt_number"

    rows = execute_query(query, params) or []

    # Group by student → subject → attempts
    grouped = {}
    for r in rows:
        sid = r['student_id']
        sub = r['subject_id']
        if sid not in grouped:
            grouped[sid] = {
                'name':       r['name'],
                'department': r['department'],
                'subjects':   {}
            }
        if sub not in grouped[sid]['subjects']:
            grouped[sid]['subjects'][sub] = {
                'subject_name': r['subject_name'],
                'attempts':     [],
                'final_status': r['status']
            }
        grouped[sid]['subjects'][sub]['attempts'].append({
            'attempt_number':   r['attempt_number'],
            'attempt_semester': r['attempt_semester'],
            'attempt_date':     r['attempt_date'],
            'marks':            r['marks'],
            'grade':            r['grade'],
            'status':           r['status'],
            'cleared_semester': r['cleared_semester']
        })
        if r['status'] == 'Cleared':
            grouped[sid]['subjects'][sub]['final_status'] = 'Cleared'

    departments = ['CSE', 'IT', 'CSM', 'CSD']
    return render_template('admin/backlogs.html',
        grouped     = grouped,
        departments = departments,
        dept_filter = dept_filter,
        admin_name  = session['admin_name']
    )

# ─────────────────────────────────────────────────────────────
# ADMIN — Prerequisite-Based Grade Prediction
# ─────────────────────────────────────────────────────────────

@app.route('/admin/predict', methods=['GET', 'POST'])
@admin_required
def admin_predict():
    """
    Admin searches for a student, picks a target subject,
    and the system predicts their grade using prerequisite grades.
    """
    prediction_result = None
    selected_student  = None
    selected_subject  = None
    prereq_grades     = []

    # Subjects that have prerequisites defined
    predictable_subjects = execute_query("""
        SELECT DISTINCT s.subject_id, s.subject_name, s.semester, s.difficulty
        FROM Subjects s
        JOIN Subject_Prerequisites sp ON sp.subject_id = s.subject_id
        ORDER BY s.semester, s.subject_name
    """) or []

    if request.method == 'POST':
        sid        = request.form.get('student_id', '').strip()
        subject_id = request.form.get('subject_id')

        if sid and subject_id:
            student = execute_query(
                "SELECT * FROM Students WHERE student_id = %s", (sid,)
            )
            if not student:
                flash('Student not found.', 'error')
                return redirect(url_for('admin_predict'))

            selected_student = student[0]
            dept = selected_student['department']

            subject = execute_query(
                "SELECT * FROM Subjects WHERE subject_id = %s", (subject_id,)
            )
            if not subject:
                flash('Subject not found.', 'error')
                return redirect(url_for('admin_predict'))

            selected_subject = subject[0]

            # Fetch prerequisite subjects and student's actual grades in them
            prereqs = execute_query("""
                SELECT sp.prereq_id, sp.weight, s.subject_name, s.difficulty
                FROM Subject_Prerequisites sp
                JOIN Subjects s ON sp.prereq_id = s.subject_id
                WHERE sp.subject_id = %s
                ORDER BY sp.weight DESC
            """, (subject_id,)) or []

            grade_point_map = {'O':10,'A':9,'B':8,'C':7,'D':6,'F':0}

            for p in prereqs:
                grade_row = execute_query("""
                    SELECT g.grade, gp.points
                    FROM Grades g
                    JOIN GradePoints gp ON g.grade = gp.grade
                    WHERE g.student_id = %s AND g.subject_id = %s
                    LIMIT 1
                """, (sid, p['prereq_id']))

                if grade_row:
                    grade  = grade_row[0]['grade']
                    points = float(grade_row[0]['points'])
                else:
                    grade  = 'N/A'
                    points = None

                prereq_grades.append({
                    'subject_name': p['subject_name'],
                    'weight':       float(p['weight']),
                    'grade':        grade,
                    'points':       points
                })

            # Only predict if we have at least one prereq grade
            available = [p for p in prereq_grades if p['points'] is not None]
            if available:
                predicted_grade, confidence = predict_prereq_grade(
                    prereq_grades        = available,
                    target_difficulty    = selected_subject['difficulty'],
                    student_cgpa         = get_cgpa(sid, dept)
                )
                prediction_result = {
                    'predicted_grade': predicted_grade,
                    'confidence':      confidence
                }

                # Store prediction in DB
                execute_query("""
                    INSERT INTO Predictions (student_id, subject_id, predicted_grade, confidence)
                    VALUES (%s, %s, %s, %s)
                """, (sid, subject_id, predicted_grade, confidence), fetch=False)
            else:
                flash('No prerequisite grades found for this student. Cannot predict.', 'warning')

    # For GET: fetch all students for search dropdown
    all_students = execute_query(
        "SELECT student_id, name, department FROM Students ORDER BY department, name"
    ) or []

    return render_template('admin/predict.html',
        admin_name           = session['admin_name'],
        predictable_subjects = predictable_subjects,
        all_students         = all_students,
        selected_student     = selected_student,
        selected_subject     = selected_subject,
        prereq_grades        = prereq_grades,
        prediction_result    = prediction_result
    )

@app.route('/admin/predict/batch', methods=['POST'])
@admin_required
def batch_predict():
    """
    Batch prediction: run prerequisite prediction for ALL students
    in a branch for a given target subject. Returns JSON for AJAX.
    """
    dept       = request.form.get('department')
    subject_id = request.form.get('subject_id')

    if not dept or not subject_id:
        return jsonify({'error': 'Missing department or subject'}), 400

    students = execute_query(
        "SELECT student_id, name FROM Students WHERE department = %s", (dept,)
    ) or []

    prereqs = execute_query("""
        SELECT sp.prereq_id, sp.weight, s.subject_name, s.difficulty
        FROM Subject_Prerequisites sp
        JOIN Subjects s ON sp.prereq_id = s.subject_id
        WHERE sp.subject_id = %s
    """, (subject_id,)) or []

    results = []
    for stu in students:
        sid = stu['student_id']
        prereq_grades = []
        for p in prereqs:
            grade_row = execute_query("""
                SELECT g.grade, gp.points
                FROM Grades g
                JOIN GradePoints gp ON g.grade = gp.grade
                WHERE g.student_id = %s AND g.subject_id = %s LIMIT 1
            """, (sid, p['prereq_id']))
            if grade_row:
                prereq_grades.append({
                    'subject_name': p['subject_name'],
                    'weight':       float(p['weight']),
                    'grade':        grade_row[0]['grade'],
                    'points':       float(grade_row[0]['points'])
                })

        if prereq_grades:
            subject_row = execute_query(
                "SELECT difficulty FROM Subjects WHERE subject_id = %s", (subject_id,)
            )
            difficulty = subject_row[0]['difficulty'] if subject_row else 'Medium'
            cgpa       = get_cgpa(sid, dept)

            predicted_grade, confidence = predict_prereq_grade(
                prereq_grades     = prereq_grades,
                target_difficulty = difficulty,
                student_cgpa      = cgpa
            )

            # Save to DB
            execute_query("""
                INSERT INTO Predictions (student_id, subject_id, predicted_grade, confidence)
                VALUES (%s, %s, %s, %s)
            """, (sid, subject_id, predicted_grade, confidence), fetch=False)

            results.append({
                'student_id':      sid,
                'name':            stu['name'],
                'predicted_grade': predicted_grade,
                'confidence':      confidence
            })
        else:
            results.append({
                'student_id':      sid,
                'name':            stu['name'],
                'predicted_grade': 'N/A',
                'confidence':      0
            })

    return jsonify({'results': results})

# ─────────────────────────────────────────────────────────────
# ADMIN — Student Profile (read-only full view)
# ─────────────────────────────────────────────────────────────

@app.route('/admin/student/<sid>')
@admin_required
def student_profile(sid):
    student = execute_query("SELECT * FROM Students WHERE student_id = %s", (sid,))
    if not student:
        flash('Student not found.', 'error')
        return redirect(url_for('manage_students'))

    s    = student[0]
    dept = s['department']
    current_sem = s.get('current_semester', 6)

    cgpa                  = get_cgpa(sid, dept)
    backlogs              = get_backlogs(sid, dept)
    backlog_history       = get_backlog_history(sid)
    semester_data         = get_semester_data(sid, dept)
    sgpa_history          = [float(r['sgpa']) for r in semester_data if r.get('sgpa')]
    dept_rank, dept_total = get_dept_rank(sid, dept)
    credits_earned, total_credits = get_credits_summary(sid, dept)
    year_sem_label        = get_year_sem_label(current_sem)

    prediction = None
    trend      = get_trend(sgpa_history)
    if len(sgpa_history) >= 2:
        prediction = predict_next_sgpa(sgpa_history)

    # Latest predictions from DB for this student
    past_predictions = execute_query("""
        SELECT p.predicted_grade, p.confidence, p.predicted_at,
               s.subject_name
        FROM Predictions p
        JOIN Subjects s ON p.subject_id = s.subject_id
        WHERE p.student_id = %s
        ORDER BY p.predicted_at DESC
        LIMIT 10
    """, (sid,)) or []

    all_grades = execute_query("""
        SELECT g.grade, g.marks, s.subject_name, s.credits,
            g.semester_id AS semester_number, gp.points
        FROM Grades g
        JOIN Subjects s     ON g.subject_id = s.subject_id
        JOIN GradePoints gp ON g.grade      = gp.grade
        WHERE g.student_id = %s
        ORDER BY g.semester_id, s.subject_name
    """, (sid,)) or []

    chart_sems     = [f"Sem {r['semester_number']}" for r in semester_data]
    chart_sgpas    = sgpa_history
    chart_subjects = [g['subject_name'][:16] for g in all_grades]
    chart_marks    = [g['marks'] for g in all_grades]

    # Convert date objects to strings for JSON serialization
    for g in all_grades:
        if hasattr(g.get('recorded_date', ''), 'isoformat'):
            g['recorded_date'] = g['recorded_date'].isoformat()

    return render_template('admin/student_profile.html',
        student_name     = s['name'],
        student_id       = sid,
        department       = dept,
        email            = s.get('email', ''),
        cgpa             = cgpa,
        backlogs         = backlogs,
        backlog_history  = backlog_history,
        semester_data    = semester_data,
        all_grades       = all_grades,
        dept_rank        = dept_rank,
        dept_total       = dept_total,
        prediction       = prediction,
        trend            = trend,
        risk_flag        = s.get('risk_flag', 'LOW'),
        db_trend         = s.get('trend', 'Stable'),
        credits_earned   = credits_earned,
        total_credits    = total_credits,
        year_sem_label   = year_sem_label,
        current_semester = current_sem,
        past_predictions = past_predictions,
        chart_sems       = chart_sems,
        chart_sgpas      = chart_sgpas,
        chart_subjects   = chart_subjects,
        chart_marks      = chart_marks,
        admin_name       = session['admin_name']
    )


if __name__ == '__main__':
    app.run(debug=True)
