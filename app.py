from flask import Flask, render_template, request
import pickle
import numpy as np
from fuzzywuzzy import fuzz  # <-- Fuzzywuzzy for typo correction

# --- MODEL LOADING ---
popular_df = pickle.load(open('popular.pkl', 'rb'))
pt = pickle.load(open('pt.pkl', 'rb'))
books = pickle.load(open('books.pkl', 'rb'))
similarity_scores = pickle.load(open('similarity_scores.pkl', 'rb'))

app = Flask(__name__)


# --- 1. POPULAR BOOKS ROUTE ---
@app.route('/')
def index():
    return render_template('index.html',
                           book_name=list(popular_df['Book-Title'].values),
                           author=list(popular_df['Book-Author'].values),
                           image=list(popular_df['Image-URL-M'].values),
                           votes=list(popular_df['num_ratings'].values),
                           rating=list(popular_df['avg_rating'].values)
                           )


# --- 2. RECOMMENDATION UI ROUTE ---
@app.route('/recommend')
def recommend_ui():
    return render_template('recommend.html')


# --- 3. CORE RECOMMENDATION LOGIC ROUTE ---
@app.route('/recommend_books', methods=['post'])
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

        # We use 75% threshold for better discovery (as discussed)
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
        # Get the index of the best matched book (e.g., 'Life of Pi')
        index = np.where(pt.index == best_match)[0][0]

        # Collaborative Filtering: Get similar items (skipping the book itself [1:] and taking next 4)
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
                # Fallback for missing ISBN data (to prevent crash)
                item.extend(["#", "#"])

            data.append(item)

        # Success: Render the recommendations along with the corrected search term
        return render_template('recommend.html', data=data, search_term=best_match)

    except IndexError:
        # This catches if the best_match title somehow couldn't be indexed (Critical System Error)
        return render_template('recommend.html', data=[],
                               error_message="A critical indexing error occurred. The book might be missing from the model. Please try another popular book title.")


if __name__ == '__main__':
    app.run(debug=True)