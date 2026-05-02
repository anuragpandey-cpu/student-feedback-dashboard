from flask import Flask, render_template, request, redirect, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from textblob import TextBlob
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = "secretkey"

# ---------------- DATABASE CONFIG ----------------
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ---------------- MODELS ----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'Student' or 'Teacher'

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    department = db.Column(db.String(50), nullable=False)
    feedback_text = db.Column(db.Text, nullable=False)
    sentiment = db.Column(db.String(20), nullable=False)

# ---------------- INITIALIZATION ----------------
def init_db():
    with app.app_context():
        db.drop_all() # Resetting once to apply new schema
        db.create_all()
        # Default Teacher
        if not User.query.filter_by(username='teacher').first():
            hashed_pw = generate_password_hash('teacher123')
            teacher = User(username='teacher', password=hashed_pw, role='Teacher')
            db.session.add(teacher)
        # Default Student
        if not User.query.filter_by(username='student').first():
            hashed_pw = generate_password_hash('student123')
            student = User(username='student', password=hashed_pw, role='Student')
            db.session.add(student)
        db.session.commit()

# ---------------- LOGIN ----------------
@app.route('/')
def login():
    if 'user' in session:
        if session.get('role') == 'Teacher':
            return redirect("/dashboard")
        return redirect("/feedback")
    return render_template("login.html")

@app.route('/login', methods=['POST'])
def do_login():
    username = request.form['username']
    password = request.form['password']
    role = request.form['role']

    user = User.query.filter_by(username=username, role=role).first()
    
    if user and check_password_hash(user.password, password):
        session['user'] = username
        session['role'] = role
        flash(f"Welcome back, {username}!", "success")
        if role == 'Teacher':
            return redirect("/dashboard")
        return redirect("/feedback")
    else:
        flash("Invalid credentials for the selected role.", "danger")
        return redirect("/")

# ---------------- FEEDBACK PAGE ----------------
@app.route('/feedback')
def feedback():
    if 'user' not in session:
        return redirect("/")
    return render_template("feedback.html", role=session.get('role'))

@app.route('/submit', methods=['POST'])
def submit():
    if 'user' not in session or session.get('role') != 'Student':
        flash("Only students can submit feedback.", "danger")
        return redirect("/")

    department = request.form['department']
    feedback_text = request.form['feedback']

    analysis = TextBlob(feedback_text)
    polarity = analysis.sentiment.polarity

    if polarity > 0.1:
        sentiment = "Positive"
    elif polarity < -0.1:
        sentiment = "Negative"
    else:
        sentiment = "Neutral"

    new_feedback = Feedback(department=department, feedback_text=feedback_text, sentiment=sentiment)
    db.session.add(new_feedback)
    db.session.commit()

    flash("Feedback submitted successfully!", "success")
    return redirect("/feedback") 

# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    if 'user' not in session or session.get('role') != 'Teacher':
        flash("Access restricted to teachers.", "danger")
        return redirect("/")
        
    all_feedback = Feedback.query.all()
    
    # Process stats
    positive = sum(1 for f in all_feedback if f.sentiment == 'Positive')
    neutral = sum(1 for f in all_feedback if f.sentiment == 'Neutral')
    negative = sum(1 for f in all_feedback if f.sentiment == 'Negative')
    
    # Use Pandas for advanced aggregation as per paper
    if all_feedback:
        df = pd.DataFrame([{
            'department': f.department,
            'sentiment': f.sentiment
        } for f in all_feedback])
        
        # Department stats (total)
        dept_counts = df['department'].value_counts().to_dict()
        dept_stats = list(dept_counts.items())
        
        # Sentiment by department for Bar Chart
        dept_sentiment = df.groupby(['department', 'sentiment']).size().unstack(fill_value=0).to_dict(orient='index')
    else:
        dept_stats = []
        dept_sentiment = {}
    
    # Calculate Health Score (Percentage of Positive & Neutral feedback)
    total_feedback = len(all_feedback)
    health_score = round(((positive + neutral) / total_feedback) * 100) if total_feedback > 0 else 0
    
    return render_template("dashboard.html",
                           positive=positive,
                           neutral=neutral,
                           negative=negative,
                           total=total_feedback,
                           health_score=health_score,
                           recent_feedback=all_feedback[::-1][:10], 
                           dept_stats=dept_stats,
                           dept_sentiment=dept_sentiment)

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect("/")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)