# AcadTrack Pro

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Flask](https://img.shields.io/badge/Flask-WebApp-green)
![MySQL](https://img.shields.io/badge/MySQL-Database-orange)
![ML](https://img.shields.io/badge/MachineLearning-ScikitLearn-red)
![License](https://img.shields.io/badge/License-Academic-lightgrey)

> **Academic Performance Tracking & Grade Prediction System for Engineering Colleges**

AcadTrack Pro is a full-stack web application designed for **NNRG (Nalla Narasimha Reddy Group of Institutions)** under the **R22 Regulations curriculum**.

The platform provides students with a **personalized academic dashboard** while giving administrators **powerful tools to manage academic records, monitor performance, track backlogs, and predict future grades using machine learning models.**

---

# Features

## Student Portal

### Academic Dashboard

* CGPA display with department ranking
* Semester-wise **SGPA trend charts**
* Subject-wise **marks chart with semester tabs**
* **Credits completion progress bar**

### Backlog Tracking

* Full attempt history for failed subjects
* Visual backlog chains
  Example:

```
Sem 3: F → Sem 4: F → Sem 5: C
```

### Semester Reports

Detailed grade sheet per semester including:

* Subject marks
* Credits
* Grade points
* SGPA calculation

### ML Prediction

Predicts **next semester SGPA** using **Ridge Regression** trained on historical student performance.

### Risk Assessment

Automated performance analysis:

| Risk Level | Meaning                        |
| ---------- | ------------------------------ |
| LOW        | Stable academic performance    |
| MEDIUM     | Slight decline detected        |
| HIGH       | At risk of academic difficulty |

Trend indicators:

* Improving
* Declining
* Stable
* At Risk

---

## Admin Portal

### Overview Dashboard

Admin overview showing:

* Total students
* Active backlogs
* Backlog clearance rate
* Branch-wise backlog distribution

### Student Management

Admins can:

* Add new students
* Delete students
* Search by name or roll number
* Filter students by branch

### Grade Management

* Add grades
* Delete grades
* Filter by branch and semester
* Automatic backlog tracking when **F grade** is entered

### Department Rankings

Displays CGPA rankings including:

* Rank
* Student CGPA
* Backlog count
* Performance classification

| CGPA Range | Status       |
| ---------- | ------------ |
| ≥ 8.0      | Distinction  |
| 7.0 – 7.99 | First Class  |
| 6.0 – 6.99 | Second Class |

### Backlog Tracker

Shows complete backlog histories for all branches including full attempt chains.

### Grade Predictor

Predicts a student's **expected grade in a subject** based on their performance in prerequisite subjects.

Supports **batch prediction for entire branches**.

---

# Screenshots

*(Add screenshots after deploying the project)*

```
docs/
dashboard.png
semester_report.png
admin_panel.png
```

Example section:

## Student Dashboard

![Dashboard](docs/dashboard.png)

## Semester Report

![Semester Report](docs/semester_report.png)

## Admin Panel

![Admin Panel](docs/admin_panel.png)

---

# Tech Stack

| Layer            | Technology                                |
| ---------------- | ----------------------------------------- |
| Backend          | Python 3 + Flask                          |
| Database         | MySQL 8.x                                 |
| Machine Learning | scikit-learn                              |
| Frontend         | HTML5, CSS3, Vanilla JS                   |
| Charts           | Chart.js                                  |
| Model Storage    | joblib (.pkl files)                       |
| Database Access  | Raw SQL via custom `execute_query` helper |

---

# System Architecture

```
Students/Admin
      │
      ▼
Flask Web Application
      │
      ▼
MySQL Database
      │
      ▼
Machine Learning Prediction Engine
(Ridge Regression + Random Forest)
```

---

# Project Structure

```
acadtrack_pro/
│
├── app.py
├── db.py
├── train_model.py
│
├── ml/
│   ├── predictor.py
│   ├── cgpa_model.pkl
│   └── prereq_model.pkl
│
├── static/
│   └── css/
│       └── style.css
│
├── templates/
│   ├── login.html
│   ├── dashboard.html
│   ├── semester_report.html
│   │
│   └── admin/
│       ├── admin_login.html
│       ├── admin_panel.html
│       ├── manage_students.html
│       ├── manage_grades.html
│       ├── rankings.html
│       ├── backlogs.html
│       ├── predict.html
│       └── student_profile.html
│
└── sql/
    ├── 01_schema.sql
    ├── 02_seeds.sql
    └── 03_data.sql
```

---

# Database Schema

The system uses **12 tables**.

| Table                    | Description                          |
| ------------------------ | ------------------------------------ |
| students                 | Core student records                 |
| semesters                | Reference table for semester numbers |
| gradepoints              | Grade to point mapping               |
| subjects                 | Subject catalog                      |
| branch_subjects          | Branch-semester subject mapping      |
| subject_prerequisites    | ML prerequisite relationships        |
| grades                   | All student grades                   |
| backlog_attempts         | History of failed subject attempts   |
| student_semester_status  | Semester completion data             |
| predictions              | Stored ML predictions                |
| prediction_training_data | Training dataset                     |
| admins                   | Admin credentials                    |

---

# Database Views

| View              | Description                     |
| ----------------- | ------------------------------- |
| v_student_cgpa    | Precomputed CGPA per student    |
| v_backlog_summary | Active uncleared backlogs       |
| v_year_semester   | Year-semester label (e.g., 3-2) |

---

# Curriculum Coverage

Built for **NNRG R22 Regulations** across four branches.

| Branch                         | Code | Total Credits |
| ------------------------------ | ---- | ------------- |
| Computer Science & Engineering | 05   | 160           |
| Information Technology         | 12   | 160           |
| CS with AI & ML                | 66   | 160           |
| CS with Data Science           | 67   | 160           |

Each semester contains **20 credits**.

---

# Machine Learning Models

## SGPA Predictor (Ridge Regression)

Predicts the **next semester SGPA**.

Features used:

* Last SGPA
* Average SGPA
* Trend direction
* Standard deviation
* Minimum SGPA
* Maximum SGPA
* Number of semesters completed

---

## Grade Predictor (Random Forest)

Predicts a **future subject grade** using prerequisite performance.

Features used:

* Weighted average of prerequisite grades
* Best prerequisite grade
* Worst prerequisite grade
* Standard deviation of prerequisite grades
* Subject difficulty
* Student CGPA
* Number of prerequisites

Training dataset:

* **15,000 synthetic samples**
* Real student data extracted from database

---

# Installation

## Prerequisites

* Python 3.10+
* MySQL 8.x
* pip

---

## 1 Clone Repository

```
git clone https://github.com/yourusername/acadtrack_pro.git
cd acadtrack_pro
```

---

## 2 Create Virtual Environment

```
python -m venv venv
```

Activate environment:

Windows

```
venv\Scripts\activate
```

Linux / Mac

```
source venv/bin/activate
```

---

## 3 Install Dependencies

```
pip install flask pymysql scikit-learn joblib numpy
```

---

## 4 Configure Database

Edit **db.py**

```python
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'your_password',
    'database': 'acadtrack_pro'
}
```

---

## 5 Setup Database

Run SQL scripts in order.

```
mysql -u root -p < sql/01_schema.sql
mysql -u root -p < sql/02_seeds.sql
mysql -u root -p < sql/03_data.sql
```

---

## 6 Train Machine Learning Models

```
python train_model.py
```

Expected output:

```
✓ cgpa_model.pkl saved
✓ prereq_model.pkl saved
Training complete. Models ready.
```

---

## 7 Run Application

```
python app.py
```

Open in browser:

```
http://127.0.0.1:5000
```

---

# Default Credentials

## Admin

| Username | Password |
| -------- | -------- |
| admin    | admin123 |

---

## Students

Each student's password is their **roll number**.

Examples:

| Roll Number | Branch | Batch |
| ----------- | ------ | ----- |
| 217Z1A0501  | CSE    | 2021  |
| 227Z1A6601  | CSM    | 2022  |
| 237Z1A6701  | CSD    | 2023  |
| 247Z1A1201  | IT     | 2024  |

---

# Roll Number Format

```
YY 7Z1A BB NNN
```

| Section | Meaning        |
| ------- | -------------- |
| YY      | Joining year   |
| BB      | Branch code    |
| NNN     | Student serial |

Example:

```
237Z1A0523
```

CSE student, joined **2023**, serial **23**.

---

# Seed Dataset

The system includes **realistic simulated academic data**.

| Metric                 | Value     |
| ---------------------- | --------- |
| Total students         | 508       |
| Batches                | 2021-2024 |
| Total grade records    | ~23,700   |
| Students with backlogs | ~81       |
| Backlog chains         | ~88       |
| Backlog clearance rate | ~72%      |

Grade distribution:

| Grade | Percentage |
| ----- | ---------- |
| O     | 12%        |
| A     | 20%        |
| B     | 24%        |
| C     | 23%        |
| D     | 13%        |
| F     | 8%         |

---

# Retraining Models

After inserting new grades or students:

```
python train_model.py
```

The optimized training script uses **bulk SQL queries** to retrain models in seconds regardless of dataset size.

---

# Future Improvements

* Deep learning based grade prediction
* Attendance analytics integration
* Notification system for backlog risk
* Mobile responsive UI
* Role-based authentication system

---

# Contributing

Pull requests are welcome. For major changes, please open an issue first.

---

# Author

**Harshith Sana**

Developed for academic purposes at
**NNRG – Nalla Narasimha Reddy Group of Institutions**
under **R22 Regulations**.

---

# License

This project is intended for **academic and educational purposes**.
