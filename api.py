from flask import Flask, request, jsonify
from hybrid import ReccobeatsAPI, get_hybrid_recommendations_for_user

app = Flask(__name__)

@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    track_id = request.args.get('track_id')
    k = int(request.args.get('k', 6))
    
    api = ReccobeatsAPI()
    recs = api.get_enhanced_recommendations(
        spotify_track_id=track_id,
        final_recommendations_count=k
    )
    
    return jsonify({
        'seed_track': track_id,
        'recommendations': [
            {'track_id': r['track_id'], 'track_name': r['track_name'],
             'artists': r['artists'], 'similarity_score': r['similarity_score']}
            for r in recs
        ]
    })

@app.route('/api/hybrid', methods=['POST'])
def get_hybrid():
    data = request.get_json()
    favourites = data.get('favourites', [])
    k = data.get('k', 6)
    
    recs, alpha, debug = get_hybrid_recommendations_for_user(favourites, k=k)
    
    return jsonify({
        'alpha': alpha,
        'mode': debug.get('mode'),
        'recommendations': [
            {'track_id': r['track_id'], 'track_name': r['track_name'],
             'artists': r['artists'], 'similarity_score': r['similarity_score'],
             'source': r.get('source')}
            for r in recs
        ]
    })

if __name__ == '__main__':
    app.run(port=5000)