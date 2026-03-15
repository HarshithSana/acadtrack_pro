"""
ml/predictor.py (Optimized)
----------------------------
Two prediction systems:

1. SGPA Predictor (Ridge Regression)
   - Better feature engineering (trend, std, avg instead of raw padded history)
   - predict_next_sgpa(sgpa_history) → predicted next semester SGPA

2. Prerequisite Grade Predictor (Random Forest)
   - Models cached in memory (no disk I/O on each prediction)
   - Balanced class weights for rare grades (O, F)
   - Proper confidence normalization
   - predict_prereq_grade(prereq_grades, target_difficulty, student_cgpa)
"""

import os
import numpy as np
import joblib

MODEL_PATH        = os.path.join(os.path.dirname(__file__), 'cgpa_model.pkl')
PREREQ_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'prereq_model.pkl')

GRADE_POINTS = {'O': 10, 'A': 9, 'B': 8, 'C': 7, 'D': 6, 'F': 0}
DIFF_MAP     = {'Easy': 0, 'Medium': 1, 'Hard': 2}
GRADE_DECODE = {5: 'O', 4: 'A', 3: 'B', 2: 'C', 1: 'D', 0: 'F'}
GRADE_ENCODE = {'O': 5, 'A': 4, 'B': 3, 'C': 2, 'D': 1, 'F': 0}

# ── Model cache (loaded once, reused) ────────────────────────
_sgpa_model   = None
_prereq_model = None

def _load_sgpa_model():
    global _sgpa_model
    if _sgpa_model is None and os.path.exists(MODEL_PATH):
        _sgpa_model = joblib.load(MODEL_PATH)
    return _sgpa_model

def _load_prereq_model():
    global _prereq_model
    if _prereq_model is None and os.path.exists(PREREQ_MODEL_PATH):
        _prereq_model = joblib.load(PREREQ_MODEL_PATH)
    return _prereq_model

def reload_models():
    """Call this after retraining to refresh cached models."""
    global _sgpa_model, _prereq_model
    _sgpa_model   = None
    _prereq_model = None

# ─────────────────────────────────────────────────────────────
# 1. SGPA MODEL — Training (Ridge Regression)
# ─────────────────────────────────────────────────────────────

def _extract_sgpa_features(sgpa_list, target_idx):
    """
    Extract meaningful features from SGPA history.
    Better than raw padded history.

    Features:
        - target_sem_number  : which semester we're predicting
        - last_sgpa          : most recent SGPA
        - avg_sgpa           : historical average
        - trend              : direction (recent[-1] - recent[0])
        - std_dev            : volatility
        - n_sems             : how many sems of history
        - min_sgpa           : worst semester
        - max_sgpa           : best semester
    """
    prev    = sgpa_list[:target_idx]
    n       = len(prev)
    avg     = sum(prev) / n
    std     = float(np.std(prev)) if n > 1 else 0.0
    recent  = prev[-3:] if n >= 3 else prev
    trend   = recent[-1] - recent[0] if len(recent) > 1 else 0.0
    return [
        target_idx + 1,      # semester number (1-indexed)
        prev[-1],            # last SGPA
        avg,                 # historical average
        trend,               # recent trend
        std,                 # volatility
        n,                   # semesters of history
        min(prev),           # worst semester
        max(prev),           # best semester
    ]


def train_sgpa_model(all_student_sgpa_data):
    """
    Train Ridge Regression on improved SGPA features.
    Ridge handles multicollinearity better than plain LinearRegression.
    """
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline

    X, y = [], []
    for sgpa_list in all_student_sgpa_data:
        if len(sgpa_list) < 2:
            continue
        for i in range(1, len(sgpa_list)):
            features = _extract_sgpa_features(sgpa_list, i)
            X.append(features)
            y.append(sgpa_list[i])

    if not X:
        print("[ML] Not enough SGPA data to train.")
        return None

    # Pipeline: StandardScaler + Ridge
    model = Pipeline([
        ('scaler', StandardScaler()),
        ('ridge',  Ridge(alpha=1.0))
    ])
    model.fit(np.array(X), np.array(y))
    joblib.dump(model, MODEL_PATH)
    print(f"[ML] SGPA model (Ridge) trained on {len(X)} samples → {MODEL_PATH}")
    return model

# Keep alias for backward compatibility
train_model = train_sgpa_model


# ─────────────────────────────────────────────────────────────
# 2. PREREQ MODEL — Training (Random Forest, Optimized)
# ─────────────────────────────────────────────────────────────

def train_prereq_model(training_rows):
    """
    Train Random Forest with:
    - class_weight='balanced' for rare grades (O, F)
    - max_depth=10 to prevent overfitting
    - min_samples_split=5 for generalization
    - Expanded features (std_dev of prereqs added)
    """
    from sklearn.ensemble import RandomForestClassifier

    X, y = [], []
    for row in training_rows:
        pts = row['prereq_points']
        if not pts:
            continue

        avg    = sum(pts) / len(pts)
        std    = float(np.std(pts)) if len(pts) > 1 else 0.0
        feat   = [
            avg,                                    # weighted avg prereq
            min(pts),                               # worst prereq
            max(pts),                               # best prereq
            std,                                    # prereq consistency
            DIFF_MAP.get(row['difficulty'], 1),     # difficulty encoded
            row.get('cgpa', 7.0),                   # student CGPA
            len(pts),                               # number of prereqs
        ]
        X.append(feat)
        y.append(GRADE_ENCODE.get(row['outcome_grade'], 2))

    if not X:
        print("[ML] Not enough prereq data to train.")
        return None

    model = RandomForestClassifier(
        n_estimators    = 200,
        max_depth       = 10,          # prevent overfitting
        min_samples_split = 5,         # generalization
        class_weight    = 'balanced',  # handle rare grades (O, F)
        random_state    = 42,
        n_jobs          = -1,          # use all CPU cores
    )
    model.fit(np.array(X), np.array(y))
    joblib.dump(model, PREREQ_MODEL_PATH)
    print(f"[ML] Prereq model (RF balanced) trained on {len(X)} samples → {PREREQ_MODEL_PATH}")
    return model


# ─────────────────────────────────────────────────────────────
# 3. PREREQ PREDICTION
# ─────────────────────────────────────────────────────────────

def predict_prereq_grade(prereq_grades, target_difficulty, student_cgpa=7.0):
    """
    Predict grade using cached ML model.
    Confidence normalized: 6-class problem baseline = 16.7%,
    so we scale to show meaningful 0-100%.
    """
    total_weight = sum(p['weight'] for p in prereq_grades)
    if total_weight == 0:
        return 'C', 50.0

    weighted_pts = [p['points'] * p['weight'] for p in prereq_grades]
    weighted_avg = sum(weighted_pts) / total_weight
    raw_pts      = [p['points'] for p in prereq_grades]
    min_pts      = min(raw_pts)
    max_pts      = max(raw_pts)
    std_pts      = float(np.std(raw_pts)) if len(raw_pts) > 1 else 0.0
    diff_enc     = DIFF_MAP.get(target_difficulty, 1)

    features = np.array([[
        weighted_avg,
        min_pts,
        max_pts,
        std_pts,
        diff_enc,
        student_cgpa,
        len(prereq_grades),
    ]])

    model = _load_prereq_model()
    if model:
        pred_class = int(model.predict(features)[0])
        proba      = model.predict_proba(features)[0]
        raw_conf   = float(max(proba))

        # Normalize: 6 classes → random baseline = 16.7%
        # Scale so baseline=16.7% maps to 40%, perfect=100% maps to 99%
        normalized_conf = round(40 + (raw_conf - 0.167) / (1.0 - 0.167) * 59, 1)
        confidence = max(40.0, min(99.0, normalized_conf))

        pred_grade = GRADE_DECODE.get(pred_class, 'C')
    else:
        pred_grade, confidence = _fallback_predict(
            weighted_avg, diff_enc, student_cgpa
        )

    return pred_grade, confidence


def _fallback_predict(weighted_avg, diff_enc, cgpa):
    penalty = {0: 0.0, 1: 0.5, 2: 1.0}.get(diff_enc, 0.5)
    score   = float(np.clip((weighted_avg * 0.6 + cgpa * 0.4) - penalty, 0.0, 10.0))

    if   score >= 9.0: return 'O', 70.0
    elif score >= 8.0: return 'A', 72.0
    elif score >= 7.0: return 'B', 68.0
    elif score >= 6.0: return 'C', 65.0
    elif score >= 5.0: return 'D', 60.0
    else:              return 'F', 55.0


# ─────────────────────────────────────────────────────────────
# 4. SGPA PREDICTION
# ─────────────────────────────────────────────────────────────

def predict_next_sgpa(sgpa_history):
    """
    Predict next semester SGPA using Ridge Regression with
    improved features and realistic clamping.
    """
    if len(sgpa_history) < 2:
        return None

    model = _load_sgpa_model()
    if not model:
        return None

    next_sem = len(sgpa_history) + 1
    features = np.array([_extract_sgpa_features(sgpa_history, next_sem - 1)])

    raw_pred  = float(model.predict(features)[0])

    # Clamp within student's realistic performance range
    hist_mean = float(np.mean(sgpa_history))
    hist_std  = float(np.std(sgpa_history)) if len(sgpa_history) > 1 else 0.5
    hist_min  = min(sgpa_history)
    hist_max  = max(sgpa_history)

    lower = max(0.0,  hist_mean - max(1.5 * hist_std, 0.8), hist_min - 0.5)
    upper = min(10.0, hist_mean + max(1.5 * hist_std, 0.8), hist_max + 0.5)

    # Blend with trend for smoother prediction
    recent     = sgpa_history[-3:] if len(sgpa_history) >= 3 else sgpa_history
    trend_step = (recent[-1] - recent[0]) / max(len(recent) - 1, 1)
    trend_pred = recent[-1] + trend_step * 0.3
    blended    = raw_pred * 0.6 + trend_pred * 0.4

    predicted_sgpa = round(float(np.clip(blended, lower, upper)), 2)
    all_sgpas      = sgpa_history + [predicted_sgpa]
    predicted_cgpa = round(float(np.mean(all_sgpas)), 2)

    n = len(sgpa_history)
    if   n >= 6: confidence, pct = 'high',   90
    elif n >= 4: confidence, pct = 'high',   85
    elif n >= 2: confidence, pct = 'medium', 70
    else:        confidence, pct = 'low',    50

    return {
        'predicted_sgpa':  predicted_sgpa,
        'predicted_cgpa':  predicted_cgpa,
        'confidence':      confidence,
        'confidence_pct':  pct,
        'next_semester':   next_sem
    }


# ─────────────────────────────────────────────────────────────
# 5. TREND ANALYSIS
# ─────────────────────────────────────────────────────────────

def get_trend(sgpa_history):
    """
    Returns trend label based on SGPA history.
    At Risk threshold raised to 6.0 (D grade level).
    Uses weighted recent trend for better accuracy.
    """
    if len(sgpa_history) < 2:
        return 'Stable'

    latest = sgpa_history[-1]
    avg    = sum(sgpa_history) / len(sgpa_history)

    # At Risk: latest SGPA below 6.0 OR avg below 5.5
    if latest < 6.0 or avg < 5.5:
        return 'At Risk'

    # Use last 3 semesters for trend
    recent = sgpa_history[-3:] if len(sgpa_history) >= 3 else sgpa_history
    delta  = recent[-1] - recent[0]

    # Weight recent changes more
    if len(recent) >= 3:
        weighted_delta = (recent[-1] - recent[-2]) * 0.6 + \
                         (recent[-2] - recent[-3]) * 0.4
    else:
        weighted_delta = delta

    if weighted_delta > 0.25:
        return 'Improving'
    elif weighted_delta < -0.25:
        return 'Declining'
    return 'Stable'