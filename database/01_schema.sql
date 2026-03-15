-- ═══════════════════════════════════════════════════════════════════════
-- AcadTrack Pro — 01_schema.sql
-- Full database schema
-- Run this FIRST on a fresh database
-- ═══════════════════════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS acadtrack_pro
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE acadtrack_pro;

CREATE TABLE IF NOT EXISTS Students (
    student_id          VARCHAR(15)  PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    email               VARCHAR(100) NOT NULL UNIQUE,
    password            VARCHAR(100) NOT NULL,
    department          VARCHAR(10)  NOT NULL,
    current_semester    INT          NOT NULL DEFAULT 1,
    risk_flag           ENUM('LOW','MEDIUM','HIGH') DEFAULT 'LOW',
    trend               ENUM('Improving','Declining','Stable','At Risk') DEFAULT 'Stable',
    credits_earned      DECIMAL(5,1) NOT NULL DEFAULT 0,
    total_credits       DECIMAL(5,1) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS Semesters (
    semester_id     INT PRIMARY KEY,
    semester_number INT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS GradePoints (
    grade   VARCHAR(2)   PRIMARY KEY,
    points  DECIMAL(3,1) NOT NULL
);

CREATE TABLE IF NOT EXISTS Subjects (
    subject_id      INT AUTO_INCREMENT PRIMARY KEY,
    subject_name    VARCHAR(150) NOT NULL,
    credits         DECIMAL(3,1) NOT NULL,
    semester        INT          NOT NULL,
    difficulty      ENUM('Easy','Medium','Hard') DEFAULT 'Medium',
    UNIQUE KEY uq_subject_sem (subject_name, semester)
);

CREATE TABLE IF NOT EXISTS Branch_Subjects (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    subject_id  INT         NOT NULL,
    department  VARCHAR(10) NOT NULL,
    semester    INT         NOT NULL,
    UNIQUE KEY uq_branch_sub (subject_id, department),
    FOREIGN KEY (subject_id) REFERENCES Subjects(subject_id)
);

CREATE TABLE IF NOT EXISTS Subject_Prerequisites (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    subject_id      INT NOT NULL,
    prereq_id       INT NOT NULL,
    weight          DECIMAL(3,2) NOT NULL DEFAULT 1.00,
    UNIQUE KEY uq_prereq (subject_id, prereq_id),
    FOREIGN KEY (subject_id) REFERENCES Subjects(subject_id),
    FOREIGN KEY (prereq_id)  REFERENCES Subjects(subject_id)
);

CREATE TABLE IF NOT EXISTS Grades (
    grade_id        INT AUTO_INCREMENT PRIMARY KEY,
    student_id      VARCHAR(15) NOT NULL,
    subject_id      INT         NOT NULL,
    semester_id     INT         NOT NULL,
    marks           INT         NOT NULL,
    grade           VARCHAR(2)  NOT NULL,
    recorded_date   DATE        NOT NULL,
    UNIQUE KEY uq_grade (student_id, subject_id, semester_id),
    FOREIGN KEY (student_id)  REFERENCES Students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id)  REFERENCES Subjects(subject_id),
    FOREIGN KEY (semester_id) REFERENCES Semesters(semester_id)
);

CREATE TABLE IF NOT EXISTS Backlog_Attempts (
    attempt_id          INT AUTO_INCREMENT PRIMARY KEY,
    student_id          VARCHAR(15) NOT NULL,
    subject_id          INT         NOT NULL,
    attempt_number      INT         NOT NULL,
    attempt_semester    INT         NOT NULL,
    attempt_date        DATE        NOT NULL,
    marks               INT         NOT NULL,
    grade               VARCHAR(2)  NOT NULL,
    status              ENUM('Cleared','Failed') NOT NULL,
    cleared_semester    INT         DEFAULT NULL,
    UNIQUE KEY uq_attempt (student_id, subject_id, attempt_number),
    FOREIGN KEY (student_id) REFERENCES Students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES Subjects(subject_id)
);

CREATE TABLE IF NOT EXISTS Student_Semester_Status (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    student_id      VARCHAR(15)  NOT NULL,
    semester_id     INT          NOT NULL,
    status          ENUM('Completed','Ongoing','Upcoming') NOT NULL DEFAULT 'Upcoming',
    sgpa            DECIMAL(4,2) DEFAULT NULL,
    completion_date DATE         DEFAULT NULL,
    UNIQUE KEY uq_stu_sem (student_id, semester_id),
    FOREIGN KEY (student_id)  REFERENCES Students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (semester_id) REFERENCES Semesters(semester_id)
);

CREATE TABLE IF NOT EXISTS Predictions (
    prediction_id       INT AUTO_INCREMENT PRIMARY KEY,
    student_id          VARCHAR(15)  NOT NULL,
    subject_id          INT          NOT NULL,
    predicted_grade     VARCHAR(2)   NOT NULL,
    confidence          DECIMAL(5,2) NOT NULL,
    predicted_sgpa      DECIMAL(4,2) DEFAULT NULL,
    predicted_cgpa      DECIMAL(4,2) DEFAULT NULL,
    next_semester       INT          DEFAULT NULL,
    predicted_at        TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES Students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES Subjects(subject_id)
);

CREATE TABLE IF NOT EXISTS Prediction_Training_Data (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    subject_id          INT         NOT NULL,
    prereq_grades_json  JSON        NOT NULL,
    difficulty          ENUM('Easy','Medium','Hard') NOT NULL,
    outcome_grade       VARCHAR(2)  NOT NULL,
    source              VARCHAR(50) DEFAULT 'synthetic',
    FOREIGN KEY (subject_id) REFERENCES Subjects(subject_id)
);

CREATE TABLE IF NOT EXISTS Admins (
    admin_id    INT AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(50)  NOT NULL UNIQUE,
    password    VARCHAR(100) NOT NULL,
    created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- ── Indexes ──────────────────────────────────────────────────
CREATE INDEX idx_grades_student     ON Grades(student_id);
CREATE INDEX idx_grades_semester    ON Grades(semester_id);
CREATE INDEX idx_grades_subject     ON Grades(subject_id);
CREATE INDEX idx_grades_grade       ON Grades(grade);
CREATE INDEX idx_backlog_student    ON Backlog_Attempts(student_id);
CREATE INDEX idx_backlog_subject    ON Backlog_Attempts(subject_id);
CREATE INDEX idx_backlog_status     ON Backlog_Attempts(status);
CREATE INDEX idx_branch_dept_sem    ON Branch_Subjects(department, semester);
CREATE INDEX idx_prereq_subject     ON Subject_Prerequisites(subject_id);
CREATE INDEX idx_sem_status_student ON Student_Semester_Status(student_id);
CREATE INDEX idx_predictions_student ON Predictions(student_id);

-- ── Views ─────────────────────────────────────────────────────
CREATE OR REPLACE VIEW v_student_cgpa AS
SELECT
    st.student_id, st.name, st.department,
    st.risk_flag, st.trend, st.credits_earned,
    st.total_credits, st.current_semester,
    ROUND(
        SUM(CASE WHEN g.grade != 'F' AND s.credits > 0
                 THEN s.credits * gp.points ELSE 0 END)
        / NULLIF(SUM(CASE WHEN g.grade != 'F' AND s.credits > 0
                         THEN s.credits ELSE 0 END), 0)
    , 2) AS cgpa
FROM Students st
LEFT JOIN Grades g           ON st.student_id = g.student_id
LEFT JOIN Subjects s         ON g.subject_id  = s.subject_id
LEFT JOIN Branch_Subjects bs ON bs.subject_id = s.subject_id
                             AND bs.department = st.department
                             AND bs.semester   = g.semester_id
LEFT JOIN GradePoints gp     ON g.grade        = gp.grade
GROUP BY st.student_id, st.name, st.department,
         st.risk_flag, st.trend, st.credits_earned,
         st.total_credits, st.current_semester;

CREATE OR REPLACE VIEW v_backlog_summary AS
SELECT
    ba.student_id, st.name, st.department,
    s.subject_name, s.subject_id,
    COUNT(ba.attempt_id)   AS total_attempts,
    MAX(ba.attempt_number) AS latest_attempt,
    MAX(ba.attempt_date)   AS last_attempt_date,
    GROUP_CONCAT(ba.grade ORDER BY ba.attempt_number SEPARATOR ' → ') AS attempt_grades,
    MAX(ba.status)         AS current_status
FROM Backlog_Attempts ba
JOIN Students st ON ba.student_id = st.student_id
JOIN Subjects s  ON ba.subject_id = s.subject_id
WHERE ba.status = 'Failed'
GROUP BY ba.student_id, st.name, st.department, s.subject_name, s.subject_id;

CREATE OR REPLACE VIEW v_year_semester AS
SELECT
    student_id, current_semester,
    CEIL(current_semester / 2) AS year_number,
    IF(current_semester % 2 = 1, 1, 2) AS sem_in_year,
    CONCAT(CEIL(current_semester / 2), '-',
           IF(current_semester % 2 = 1, 1, 2)) AS year_sem_label
FROM Students;