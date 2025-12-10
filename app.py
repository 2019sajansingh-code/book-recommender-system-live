from flask import Flask, render_template, request, redirect, url_for, flash
import pickle
import numpy as np
from fuzzywuzzy import fuzz

# --- New Imports for Authentication ---
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session  # For Cart functionality

# --- MODEL LOADING (NO CHANGE HERE) ---
popular_df = pickle.load(open('popular.pkl', 'rb'))
pt = pickle.load(open('pt.pkl', 'rb'))
books = pickle.load(open('books.pkl', 'rb'))
similarity_scores = pickle.load(open('similarity_scores.pkl', 'rb'))

app = Flask(__name__)

# --- AUTHENTICATION/DB CONFIGURATION ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'your_super_secret_key_change_this'  # Zaroori!
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Agar user login nahi hai, toh yeh view dikhega
login_manager.login_message_category = 'info'


# --- USER MODEL (Database Schema) ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# User loader function for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --- ROUTE HANDLERS ---

# 1. REGISTER ROUTE
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user_exists = User.query.filter_by(username=username).first()
        if user_exists:
            flash('Username already exists. Please login.', 'danger')
            return redirect(url_for('register'))

        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# 2. LOGIN ROUTE
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash(f'Logged in successfully as {username}.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('login.html')


# 3. LOGOUT ROUTE
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# --- 4. PROFILE ROUTE ---
@app.route('/profile')
@login_required # Sirf logged-in user hi dekh sakte hain
def profile():
    # current_user object Flask-Login se aata hai, jismein user ka data hota hai
    return render_template('profile.html', user=current_user)
# 4. POPULAR BOOKS ROUTE (NOW PROTECTED)
@app.route('/')
@login_required  # Only authenticated users can see this
def index():
    return render_template('index.html',
                           book_name=list(popular_df['Book-Title'].values),
                           author=list(popular_df['Book-Author'].values),
                           image=list(popular_df['Image-URL-M'].values),
                           votes=list(popular_df['num_ratings'].values),
                           rating=list(popular_df['avg_rating'].values)
                           )


# 5. RECOMMENDATION UI ROUTE (NOW PROTECTED)
@app.route('/recommend')
@login_required
def recommend_ui():
    return render_template('recommend.html')


# 6. CORE RECOMMENDATION LOGIC ROUTE (FUZZY LOGIC & HYBRID LINKS)
@app.route('/recommend_books', methods=['post'])
@login_required
def recommend():
    user_input = request.form.get('user_input')

    # ... (Fuzzy Matching Logic - No Change from final working version) ...
    # ... (Recommendation Logic - No Change) ...

    # NOTE: Please insert the complete recommendation logic here (Steps 1, 2, 3 from last response)
    # Since I don't have the full code block of your final working recommend()
    # I am placing a placeholder. Ensure you copy the complete fixed logic here.

    # Placeholder for the final working recommend() function logic:
    # return render_template('recommend.html', data=data, search_term=best_match)

    # Example placeholder return:
    return render_template('recommend.html', data=[], error_message="Fuzzy logic needs to be inserted here.")


# --- DATABASE INITIALIZATION (Run this LOCALLY once) ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    # NOTE: Run this first locally to create the users.db file
    app.run(debug=True)