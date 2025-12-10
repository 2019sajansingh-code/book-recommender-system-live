from fuzzywuzzy import fuzz
from flask import Flask,render_template,request
import pickle
import numpy as np


popular_df = pickle.load(open('popular.pkl','rb'))
pt = pickle.load(open('pt.pkl','rb'))
books = pickle.load(open('books.pkl','rb'))
similarity_scores = pickle.load(open('similarity_scores.pkl','rb'))

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html',
                           book_name = list(popular_df['Book-Title'].values),
                           author=list(popular_df['Book-Author'].values),
                           image=list(popular_df['Image-URL-M'].values),
                           votes=list(popular_df['num_ratings'].values),
                           rating=list(popular_df['avg_rating'].values)
                           )

@app.route('/recommend')
def recommend_ui():
    return render_template('recommend.html')

@app.route('/recommend_books',methods=['post'])
def recommend():
    user_input = request.form.get('user_input')
    # 1. Initialization
    book_titles = pt.index.tolist()
    normalized_input = user_input.lower()

    best_match = None
    max_score = -1

    # 2. Iteration and Score Calculation
    for title in book_titles:
        # Score calculation (title ko lower karna zaroori hai)
        score = fuzz.ratio(title.lower(), normalized_input)

        # 3. Match Condition Check
        if score > 80 and score > max_score:  # 80 is the threshold
            max_score = score
            best_match = title

    # --- Indexing and Error Handling ---

    if best_match is None:
        # Agar koi bhi 80% se upar match nahi mila
        # Error: Yeh message dikh raha hoga (Agar aapne error handling daala hai)
        return render_template('recommend.html', error_message=f"Sorry, no close match found for '{user_input}'.")

    # 4. Success: Use best_match for recommendation
    try:
        index = np.where(pt.index == user_input)[0][0]
        similar_items = sorted(list(enumerate(similarity_scores[index])), key=lambda x: x[1], reverse=True)[1:5]


        data = []
        for i in similar_items:
           item = []
           temp_df = books[books['Book-Title'] == pt.index[i[0]]]
           item.extend(list(temp_df.drop_duplicates('Book-Title')['Book-Title'].values))
           item.extend(list(temp_df.drop_duplicates('Book-Title')['Book-Author'].values))
           item.extend(list(temp_df.drop_duplicates('Book-Title')['Image-URL-M'].values))
           try:
             isbn = list(temp_df['ISBN'].values)[0]
             book_title = list(temp_df['Book-Title'].values)[0]

            # Purchase Link (Option A)
             purchase_link = f"https://www.amazon.com/s?k={isbn}"

            # Free Ebook Search Link (Option B - Universal Search)
            # Yeh link user ko seedhe search result page par le jayega
             free_link = f"https://www.gutenberg.org/ebooks/search/?query={book_title.replace(' ', '+')}"

             item.extend([purchase_link])
             item.extend([free_link])

           except:
             item.extend(["#", "#"])
           data.append(item)



        return render_template('recommend.html', data=data, search_term=best_match)

    except IndexError:

      return render_template('recommend.html', data=data,search_term=best_match)

if __name__ == '__main__':
    app.run(debug=True)

