from flask import Flask, render_template, request, redirect, url_for, flash, session
import pickle
import numpy as np
from fuzzywuzzy import fuzz

# --- Authentication and Database Imports ---
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# --- MODEL LOADING ---
try:
    popular_df = pickle.load(open('popular.pkl', 'rb'))
    pt = pickle.load(open('pt.pkl', 'rb'))
    books = pickle.load(open('books.pkl', 'rb'))
    similarity_scores = pickle.load(open('similarity_scores.pkl', 'rb'))
except FileNotFoundError:
    print("ERROR: Model files (pkl) not found. Please ensure they are present.")
    exit()

app = Flask(__name__)

# --- AUTHENTICATION/DB CONFIGURATION ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'your_super_secret_key_change_this_for_production'
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


# --- USER MODEL ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ----------------------------------------
#          AUTHENTICATION ROUTES
# ----------------------------------------

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


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)


# ----------------------------------------
#          CART ROUTES
# ----------------------------------------

@app.route('/add_to_cart/<isbn>', methods=['POST'])
@login_required
def add_to_cart(isbn):
    if 'cart' not in session:
        session['cart'] = []

    if isbn not in session['cart']:
        session['cart'].append(isbn)
        session.modified = True
        flash('Book added to cart!', 'success')
    else:
        flash('Book is already in your cart.', 'info')

    return redirect(url_for('recommend_ui'))


@app.route('/view_cart')
@login_required
def view_cart():
    cart_isbns = session.get('cart', [])
    cart_items_list = []

    if cart_isbns:
        # Retrieve metadata for items in the cart
        cart_items_df = books[books['ISBN'].isin(cart_isbns)].drop_duplicates('ISBN')

        for index, row in cart_items_df.iterrows():
            cart_items_list.append({
                'isbn': row['ISBN'],
                'title': row['Book-Title'],
                'author': row['Book-Author'],
                'image': row['Image-URL-M']
            })

    # Final Checkout Link
    checkout_url = "https://www.amazon.com/s?k=" + "+".join(cart_isbns)

    return render_template('cart.html', items=cart_items_list, checkout_link=checkout_url)


@app.route('/remove_from_cart/<isbn>', methods=['POST'])
@login_required
def remove_from_cart(isbn):
    if 'cart' in session and isbn in session['cart']:
        session['cart'].remove(isbn)
        session.modified = True
        flash('Book removed from cart.', 'warning')
    return redirect(url_for('view_cart'))


# ----------------------------------------
#          CORE APPLICATION ROUTES
# ----------------------------------------

@app.route('/')
@login_required
def index():
    cart_count = len(session.get('cart', []))
    return render_template('index.html',
                           book_name=list(popular_df['Book-Title'].values),
                           author=list(popular_df['Book-Author'].values),
                           image=list(popular_df['Image-URL-M'].values),
                           votes=list(popular_df['num_ratings'].values),
                           rating=list(popular_df['avg_rating'].values),
                           cart_count=cart_count
                           )


@app.route('/recommend')
@login_required
def recommend_ui():
    cart_count = len(session.get('cart', []))
    return render_template('recommend.html', cart_count=cart_count)


@app.route('/recommend_books', methods=['post'])
@login_required
def recommend():
    user_input = request.form.get('user_input')
    cart_count = len(session.get('cart', []))

    # 1. FUZZY MATCHING LOGIC
    book_titles = pt.index.tolist()
    normalized_input = user_input.lower()
    best_match = None
    max_score = -1

    for title in book_titles:
        score = fuzz.ratio(title.lower(), normalized_input)
        if score > 75 and score > max_score:
            max_score = score
            best_match = title

    # --- ERROR HANDLING ---
    if best_match is None:
        return render_template('recommend.html', data=[], cart_count=cart_count,
                               error_message=f"Sorry, no book found matching '{user_input}'. Please check the spelling or try a different title.")

    # 2. CORE RECOMMENDATION & DATA RETRIEVAL
    try:
        index = np.where(pt.index == best_match)[0][0]
        similar_items = sorted(list(enumerate(similarity_scores[index])),
                               key=lambda x: x[1], reverse=True)[1:5]

        data = []
        for i in similar_items:
            item = []
            temp_df = books[books['Book-Title'] == pt.index[i[0]]].drop_duplicates('Book-Title')

            # Item Metadata (Index 0, 1, 2)
            item.extend(list(temp_df['Book-Title'].values))
            item.extend(list(temp_df['Book-Author'].values))
            item.extend(list(temp_df['Image-URL-M'].values))

            # Hybrid Link Provision (Index 3, 4) AND ISBN (Index 5)
            try:
                isbn = list(temp_df['ISBN'].values)[0]
                book_title = list(temp_df['Book-Title'].values)[0]

                # Index 3: Purchase Link
                purchase_link = f"https://www.amazon.com/s?k={isbn}"
                # Index 4: Free Ebook Search Link
                free_link = f"https://www.gutenberg.org/ebooks/search/?query={book_title.replace(' ', '+')}"

                item.extend([purchase_link])
                item.extend([free_link])
                # Index 5: ISBN (for Cart functionality)
                item.extend([isbn])

            except:
                item.extend(["#", "#", "#"])  # Fallback to maintain item length

            data.append(item)

        # Success
        return render_template('recommend.html', data=data, search_term=best_match, cart_count=cart_count)

    except IndexError:
        return render_template('recommend.html', data=[], cart_count=cart_count,
                               error_message="A critical indexing error occurred. The book might be missing from the model.")


# --- DATABASE INITIALIZATION (Run this LOCALLY once) ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)