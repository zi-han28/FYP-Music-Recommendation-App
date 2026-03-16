import re
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

class SentimentAnalyzer:
    def __init__(self):
        # 0 = Negative, 1 = Neutral, 2 = Positive
        self.model_name = 'cardiffnlp/twitter-roberta-base-sentiment-latest'
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)

    def _clean_text(self, text):
        """Removes metadata noise but keeps the actual language."""
        if not text: 
            return ""
        
        # Remove Genius section headers and common footer noise
        # Remove [Chorus], [Verse] headers
        text = re.sub(r'\[.*?\]', '', text)
        # Remove trailing embed text
        text = re.sub(r'\d*Embed$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'You might also like', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\d+Contributors?', '', text)
        
        # Clean whitespace
        text = " ".join(text.split())
        return text.strip()
        
    def analyze(self, text):
        cleaned_text = self._clean_text(text)
        
        if not cleaned_text or len(cleaned_text.strip()) < 10:
            return {"label": "Neutral", "score": 1.0, "confidence": 0.0}
        
        # Tokenize
        inputs = self.tokenizer(
            cleaned_text, 
            return_tensors="pt", 
            truncation=True, 
            max_length=512,
            padding=True
        )
        
        # Get prediction
        with torch.no_grad():
            outputs = self.model(**inputs)
            
        # Get probabilities (softmax ensures they sum to 1)
        # props = [Prob_Negative, Prob_Neutral, Prob_Positive]
        probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
        
        # --- CALCULATE WEIGHTED SCORE (0 to 2) ---
        # 0*Neg + 1*Neu + 2*Pos
        # This converts the 3 integers into a continuous float score
        neg_prob = float(probabilities[0][0])
        neu_prob = float(probabilities[0][1])
        pos_prob = float(probabilities[0][2])
        
        raw_score = (neg_prob * 0) + (neu_prob * 1) + (pos_prob * 2)
        score = round(raw_score, 2)
        
        # --- APPLY YOUR CUSTOM THRESHOLDS ---
        # logic: <= 0.5 (Neg), 0.5-1 (Slightly Neg), 1 (Neu), 1-1.5 (Slightly Pos), >1.5 (Pos)
        
        if score <= 0.5:
            label = "Negative"
        elif score < 1.0:
            label = "Slightly Negative"
        elif score == 1.0:
            label = "Neutral"
        elif score <= 1.5:
            label = "Slightly Positive"
        else:
            label = "Positive"
            
        # We define confidence as the probability of the dominant class
        confidence = max(neg_prob, neu_prob, pos_prob)
        
        return {
            "label": label,
            "score": score,  # 0.00 to 2.00
            "confidence": round(confidence, 2)
        }

# --- UNIT TEST ---
def run_unit_test():
    print("\n--- Running Unit Test ---")
    analyzer = SentimentAnalyzer()
    
    test_cases = [
        "I hate this, it is the worst day of my life.",
        "It was okay, not great but not terrible.",
        "I absolutely love this amazing song!",
        "I'm feeling a bit down but I'll survive.",
    ]
    
    for text in test_cases:
        result = analyzer.analyze(text)
        print(f"\nText: '{text}'")
        print(f"Score: {result['score']} -> Label: {result['label']}")

if __name__ == "__main__":
    run_unit_test()