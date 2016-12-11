import lib.mongo
import logging
import lib.analyze_text

def compute_rating(positive_count, neutral_count, negative_count):
    total = positive_count + neutral_count + negative_count
    if total < 5:
        return 'NEUTRAL'

    pos = positive_count/total
    neu = neutral_count/total
    neg = negative_count/total

    if pos > 0.3 and neg > 0.3:
        return 'CONTROVERSIAL'
    if pos > 0.7 or (pos > 0.5 and pos >= neg * 2):
        return 'POSITIVE'
    if neg > 0.7 or (neg > 0.5 and neg >= pos * 2):
        return 'NEGATIVE'
    return 'NEUTRAL'

def analyze_comments():
    """Runs sentiment analysis on all comments in the database; updates the
    score of each comment and the comment-sentiment fields for each docket."""

    scores = {}  # {docket_id: [comment1_score, comment2_score, ...]}
    positive_counts = {}  # {docket_id: num_positive_comments}
    neutral_counts = {}  # {docket_id: num_neutral_comments}
    negative_counts = {}  # {docket_id: num_negative_comments}

    comment_sentiments = {}  # {comment_id: sentiment} to write to database
    for comment in lib.mongo.retrieve_comments(1000):
        docket_id = comment['docketId']
        comment_id = comment['documentId']

        # Fill in the 'sentiment' field of this comment.
        text = comment.get('commentText', '').strip()
        if 'sentiment' in comment:
            score = comment['sentiment']
        else:
            score = lib.analyze_text.getSentiment(text)
            comment_sentiments[comment_id] = score
        logging.info('docket %s, comment %s: sentiment %s (%r)' %
                     (docket_id, comment_id, score, text[:20]))

        # Aggregate the scores for each docket.
        scores.setdefault(docket_id, []).append(score)
        counts = positive_counts if score > 0 else (
            negative_counts if score < 0 else neutral_counts)
        counts[docket_id] = counts.get(docket_id, 0) + 1

        if len(comment_sentiments) >= 10:
            logging.info('updating %d comments...' % len(comment_sentiments))
            lib.mongo.update_comments('sentiment', comment_sentiments)
            comment_sentiments = {}

    logging.info('updating %d comments...' % len(comment_sentiments))
    lib.mongo.update_comments('sentiment', comment_sentiments)
    logging.info('done!')

    docket_sentiments = {}  # {docket_id: sentiment} to write to database

    for docket in lib.mongo.dockets.find():
        docket_id = docket.get('docketId', '')
        positive_count = positive_counts.get(docket_id, 0)
        neutral_count = neutral_counts.get(docket_id, 0)
        negative_count = negative_counts.get(docket_id, 0)
        rating = compute_rating(positive_count, neutral_count, negative_count)
        logging.info('docket %s: %d positive, %d neutral, %d negative - %s' %
                     (docket_id, positive_count, neutral_count, negative_count,
                      rating))

        docket_sentiments[docket_id] = {
            'positive': positive_count,
            'neutral': neutral_count,
            'negative': negative_count,
            'rating': rating
        }

    logging.info('updating %d dockets...' % len(docket_sentiments))
    lib.mongo.update_dockets('sentiment', docket_sentiments)
    logging.info('done!')

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    analyze_comments()
