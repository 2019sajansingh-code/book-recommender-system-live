from flask import Flask, render_template, request, redirect, url_for, flash, session
import pickle
import numpy as np
from fuzzywuzzy import fuzz  # For typo correction

# --- New Imports for Authentication ---
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# --- MODEL LOADING ---
# Ensure these pickle files are present in your directory
try:
    popular_df = pickle.load(open('popular.pkl', 'rb'))
    pt = pickle.load(open('pt.pkl', 'rb'))
    books = pickle.load(open('books.pkl', 'rb'))
    similarity_scores = pickle.load(open('similarity_scores.pkl', 'rb'))
except FileNotFoundError:
    print("ERROR: Model files (pkl) not found. Please run the model notebook first.")
    exit()

app = Flask(__name__)

# --- AUTHENTICATION/DB CONFIGURATION ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'your_super_secret_key_change_this_for_production'  # CRITICAL: Change this!
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
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


# --- ROUTE HANDLERS: AUTHENTICATION ---

# 1. REGISTER ROUTE
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

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


# 4. PROFILE ROUTE
@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)


# --- ROUTE HANDLERS: CORE APPLICATION ---

# 5. POPULAR BOOKS ROUTE
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


# 6. RECOMMENDATION UI ROUTE
@app.route('/recommend')
@login_required
def recommend_ui():
    return render_template('recommend.html')


# 7. CORE RECOMMENDATION LOGIC (FUZZY LOGIC & HYBRID LINKS)
@app.route('/recommend_books', methods=['post'])
@login_required
def recommend():
    user_input = request.form.get('user_input')

    # 1. FUZZY MATCHING LOGIC
    book_titles = pt.index.tolist()
    normalized_input = user_input.lower()

    best_match = None
    max_score = -1

    # Find the best match title using Levenshtein ratio
    for title in book_titles:
        score = fuzz.ratio(title.lower(), normalized_input)

        # We use 75% threshold for better discovery (for typos)
        if score > 75 and score > max_score:
            max_score = score
            best_match = title

    # --- ERROR HANDLING ---

    if best_match is None:
        # If no close match found (score < 75)
        return render_template('recommend.html', data=[],
                               error_message=f"Sorry, no book found matching '{user_input}'. Please check the spelling or try a different title.")

    # 2. CORE RECOMMENDATION & DATA RETRIEVAL
    try:
        # Get the index of the best matched book
        index = np.where(pt.index == best_match)[0][0]

        # Collaborative Filtering: Get similar items
        similar_items = sorted(list(enumerate(similarity_scores[index])),
                               key=lambda x: x[1], reverse=True)[1:5]

        data = []
        for i in similar_items:
            item = []

            # Retrieve unique metadata
            temp_df = books[books['Book-Title'] == pt.index[i[0]]].drop_duplicates('Book-Title')

            # Item Metadata (Index 0, 1, 2)
            item.extend(list(temp_df['Book-Title'].values))
            item.extend(list(temp_df['Book-Author'].values))
            item.extend(list(temp_df['Image-URL-M'].values))

            # Hybrid Link Provision (Index 3, 4)
            try:
                isbn = list(temp_df['ISBN'].values)[0]
                book_title = list(temp_df['Book-Title'].values)[0]

                # Index 3: Purchase Link (Amazon)
                purchase_link = f"https://www.amazon.com/s?k={isbn}"

                # Index 4: Free Ebook Search Link (Gutenberg)
                free_link = f"https://www.gutenberg.org/ebooks/search/?query={book_title.replace(' ', '+')}"

                item.extend([purchase_link])
                item.extend([free_link])

            except:
                # Fallback for missing ISBN data
                item.extend(["#", "#"])

            data.append(item)

        # Success: Render the recommendations along with the corrected search term
        return render_template('recommend.html', data=data, search_term=best_match)

    except IndexError:
        # This catches if the best_match title somehow couldn't be indexed
        return render_template('recommend.html', data=[],
                               error_message="A critical indexing error occurred. The book might be missing from the model.")


# --- DATABASE INITIALIZATION (Run this LOCALLY once) ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    # NOTE: Run this first locally to create the users.db file
    app.run(debug=True)