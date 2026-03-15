# 🎓 AcadTrack Pro

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Flask](https://img.shields.io/badge/Flask-WebApp-green)
![MySQL](https://img.shields.io/badge/MySQL-Database-orange)
![ML](https://img.shields.io/badge/MachineLearning-ScikitLearn-red)
![License](https://img.shields.io/badge/License-Academic-lightgrey)

> 📊 **Academic Performance Tracking & Grade Prediction System for Engineering Colleges**

AcadTrack Pro is a **full-stack academic analytics platform** built using **Python, Flask, MySQL, and Machine Learning**.

The system provides students with a **personalized academic dashboard** while giving administrators powerful tools to **monitor performance, manage academic records, track backlogs, and predict future grades using machine learning models**.

---

# ✨ Features

## 🎓 Student Portal

### 📊 Academic Dashboard

* CGPA display with **department ranking**
* Semester-wise **SGPA trend charts**
* Subject-wise **marks visualization**
* **Credit completion progress bar**

---

### 🔗 Backlog Tracking

Students can track the complete history of failed subjects.

Example backlog chain:

```
Sem 3: F → Sem 4: F → Sem 5: C
```

The system records:

* number of attempts
* clearance semester
* backlog trends

---

### 📄 Semester Reports

Detailed grade sheet per semester including:

* subject marks
* credits
* grade points
* SGPA calculation
* grade distribution charts

---

### 🚨 Risk Assessment

Automatic academic risk classification.

| Risk Level | Meaning            |
| ---------- | ------------------ |
| 🟢 LOW     | Stable performance |
| 🟡 MEDIUM  | Slight decline     |
| 🔴 HIGH    | Academic risk      |

Trend indicators:

* 📈 Improving
* 📉 Declining
* ➖ Stable

---

# 🛠 Admin Portal

### 📊 Overview Dashboard

Admin overview showing:

* 👨‍🎓 total students
* ⚠️ active backlogs
* ✅ backlog clearance rate
* 🏫 branch-wise backlog distribution

---

### 👥 Student Management

Admins can:

* add students
* delete students
* search by roll number
* filter by branch

---

### 📝 Grade Management

Features include:

* add grades
* delete grades
* branch filtering
* semester filtering
* automatic backlog detection

---

### 🏆 Department Rankings

Displays CGPA rankings including:

* student rank
* CGPA
* backlog count
* performance classification

| CGPA Range | Status          |
| ---------- | --------------- |
| ≥ 8.0      | 🏅 Distinction  |
| 7.0 – 7.99 | 🥇 First Class  |
| 6.0 – 6.99 | 🥈 Second Class |

---

### 🔮 Grade Predictor (Machine Learning)

Admin tool that predicts **future subject grades** using prerequisite subject performance.

The model considers:

* prerequisite grades
* student CGPA
* subject difficulty
* statistical academic trends

Supports **batch prediction for entire branches**.

---

# 📸 Screenshots

| 🔐 Login                   | 📊 Dashboard                   | 📄 Semester Report                   |
| -------------------------- | ------------------------------ | ------------------------------------ |
| ![](screenshots/login.png) | ![](screenshots/dashboard.png) | ![](screenshots/semester_report.png) |

| 🔗 Backlog Chain                   | 🛠 Admin Dashboard                   | 🔮 Grade Prediction                   |
| ---------------------------------- | ------------------------------------ | ------------------------------------- |
| ![](screenshots/backlog_chain.png) | ![](screenshots/admin_dashboard.png) | ![](screenshots/grade_prediction.png) |

| 👥 Student Management                | 📝 Grade Management                | 🏆 Rankings                   |
| ------------------------------------ | ---------------------------------- | ----------------------------- |
| ![](screenshots/manage_students.png) | ![](screenshots/manage_grades.png) | ![](screenshots/rankings.png) |

| ⚠️ Admin Backlog Tracker      | 👤 Student Profile                   |
| ----------------------------- | ------------------------------------ |
| ![](screenshots/backlogs.png) | ![](screenshots/student_profile.png) |

---

# ⚙️ Tech Stack

| Layer            | Technology              |
| ---------------- | ----------------------- |
| Backend          | Python, Flask           |
| Database         | MySQL                   |
| Machine Learning | scikit-learn            |
| Frontend         | HTML5, CSS3, JavaScript |
| Charts           | Chart.js                |
| Model Storage    | joblib (.pkl files)     |

---

# 🏗 System Architecture

```
Students / Admin
       │
       ▼
Flask Web Application
       │
       ▼
MySQL Database
       │
       ▼
Machine Learning Engine
(Ridge Regression + Random Forest)
```

---

# 📁 Project Structure

```
acadtrack_pro/
│
├── app.py
├── db.py
├── train_model.py
├── requirements.txt
│
├── ml/
│   ├── predictor.py
│   ├── cgpa_model.pkl
│   └── prereq_model.pkl
│
├── static/
│   └── css/style.css
│
├── templates/
│   ├── login.html
│   ├── dashboard.html
│   ├── semester_report.html
│   └── admin/
│       ├── admin_panel.html
│       ├── manage_students.html
│       ├── manage_grades.html
│       ├── rankings.html
│       ├── backlogs.html
│       ├── predict.html
│       └── student_profile.html
│
├── screenshots/
│   ├── login.png
│   ├── dashboard.png
│   ├── semester_report.png
│   ├── backlog_chain.png
│   ├── admin_dashboard.png
│   ├── grade_prediction.png
│   ├── manage_students.png
│   ├── manage_grades.png
│   ├── rankings.png
│   ├── backlogs.png
│   └── student_profile.png
│
└── sql/
    ├── 01_schema.sql
    ├── 02_seeds.sql
    └── 03_data.sql
```

---

# 🗄 Database Schema

The system uses **12 tables**.

| Table                    | Description                |
| ------------------------ | -------------------------- |
| students                 | student records            |
| semesters                | semester reference         |
| gradepoints              | grade-point mapping        |
| subjects                 | subject catalog            |
| branch_subjects          | branch subject mapping     |
| subject_prerequisites    | prerequisite relationships |
| grades                   | student grades             |
| backlog_attempts         | backlog history            |
| student_semester_status  | semester status            |
| predictions              | stored ML predictions      |
| prediction_training_data | ML training dataset        |
| admins                   | admin accounts             |

---

# 🤖 Machine Learning Models

## SGPA Predictor

Model: **Ridge Regression**

Predicts **next semester SGPA** using:

* last SGPA
* average SGPA
* trend direction
* standard deviation
* min / max SGPA
* number of semesters completed

---

## Grade Predictor

Model: **Random Forest**

Predicts **future subject grades** using:

* prerequisite grades
* student CGPA
* subject difficulty
* statistical features

---

# 🚀 Installation

## Prerequisites

* Python 3.10+
* MySQL 8+
* pip

---

## Clone Repository

```
git clone https://github.com/yourusername/acadtrack_pro.git
cd acadtrack_pro
```

---

## Install Dependencies

```
pip install -r requirements.txt
```

---

## Configure Database

Edit `db.py`

```
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'your_password',
    'database': 'acadtrack_pro'
}
```

---

## Setup Database

```
mysql -u root -p < sql/01_schema.sql
mysql -u root -p < sql/02_seeds.sql
mysql -u root -p < sql/03_data.sql
```

---

## Train Machine Learning Models

```
python train_model.py
```

Expected output:

```
✓ cgpa_model.pkl saved
✓ prereq_model.pkl saved
Training complete
```

---

## Run Application

```
python app.py
```

Open in browser:

```
http://127.0.0.1:5000
```

---

# 🔑 Default Credentials

### Admin

| Username | Password |
| -------- | -------- |
| admin    | admin123 |

---

### Students

Student password = **roll number**

Example:

| Roll Number | Branch |
| ----------- | ------ |
| 217Z1A0501  | CSE    |
| 227Z1A6601  | CSM    |
| 237Z1A6701  | CSD    |
| 247Z1A1201  | IT     |

---

# 📊 Dataset Summary

| Metric                    | Value     |
| ------------------------- | --------- |
| 👨‍🎓 Students            | 508       |
| 📚 Batches                | 2021–2024 |
| 📝 Grade Records          | ~23,700   |
| ⚠️ Students with Backlogs | ~81       |
| 🔗 Backlog Chains         | ~88       |
| ✅ Clearance Rate          | ~72%      |

---

# 🔮 Future Improvements

* 📲 Mobile responsive interface
* 🔔 Academic risk notifications
* 📊 Attendance analytics integration
* 🧠 Advanced deep learning prediction models
* 🔐 Role-based authentication

---

# 👨‍💻 Author

**Harshith Sana**

Academic Software Project

---

# 📄 License

This project is intended for **academic and educational purposes**.
