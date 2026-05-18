"""
ml_classifier.py - Hybrid ML classifier for Nextflow log failure detection.

Combines:
  - TF-IDF features from raw log text
  - Structured features (exit codes, memory values, regex flags)
  - GradientBoostingClassifier for prediction
  - SHAP for explainability

Usage:
    from src.ml_classifier import MLClassifier
    clf = MLClassifier()
    clf.train(dataset)          # list of {"text": ..., "label": ...}
    result = clf.predict(log_text)
    clf.save("models/guardian_v1.pkl")
    clf.load("models/guardian_v1.pkl")
"""

import pickle
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import classification_report
from sklearn.preprocessing import LabelEncoder
from scipy.sparse import hstack, csr_matrix

from src.feature_extractor import extract_features, get_feature_names


class MLClassifier:
    """Hybrid TF-IDF + structured features classifier with SHAP support."""

    def __init__(self, n_estimators=200, max_depth=5, tfidf_max_features=5000):
        self.tfidf = TfidfVectorizer(
            ngram_range=(1, 3),
            max_features=tfidf_max_features,
            sublinear_tf=True,
            strip_accents="unicode",
            token_pattern=r"(?u)\b\w[\w./:-]+\b",  # captures paths, versions, etc.
        )
        self.clf = GradientBoostingClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=0.1,
            subsample=0.8,
            random_state=42,
        )
        self.label_encoder = LabelEncoder()
        self.feature_names = get_feature_names()
        self.is_trained = False

    def _build_features(self, texts, fit_tfidf=False):
        """Build combined feature matrix from texts."""
        # TF-IDF features
        if fit_tfidf:
            tfidf_matrix = self.tfidf.fit_transform(texts)
        else:
            tfidf_matrix = self.tfidf.transform(texts)

        # Structured features
        struct_rows = []
        for text in texts:
            feats = extract_features(text)
            row = [feats.get(name, 0) for name in self.feature_names]
            struct_rows.append(row)
        struct_matrix = csr_matrix(np.array(struct_rows, dtype=np.float64))

        # Combine
        combined = hstack([tfidf_matrix, struct_matrix])
        return combined

    def train(self, dataset, verbose=True):
        """Train the classifier on a labeled dataset.

        Args:
            dataset: list of {"text": str, "label": str} dicts
            verbose: print training metrics
        """
        texts = [item["text"] for item in dataset]
        labels = [item["label"] for item in dataset]

        y = self.label_encoder.fit_transform(labels)
        X = self._build_features(texts, fit_tfidf=True)

        if verbose:
            print(f"Training on {len(dataset)} samples, {len(self.label_encoder.classes_)} classes")
            print(f"Feature dimensions: {X.shape[1]} (TF-IDF: {self.tfidf.transform(texts[:1]).shape[1]}, structured: {len(self.feature_names)})")

            # Cross-validation
            cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
            scores = cross_val_score(self.clf, X, y, cv=cv, scoring="f1_macro")
            print(f"5-fold CV F1 (macro): {scores.mean():.3f} ± {scores.std():.3f}")

        self.clf.fit(X, y)
        self.is_trained = True

        if verbose:
            y_pred = self.clf.predict(X)
            print("\nTraining set classification report:")
            print(classification_report(
                y, y_pred,
                target_names=self.label_encoder.classes_,
                digits=3,
            ))

    def predict(self, text):
        """Predict failure category for a single log.

        Returns:
            dict with: label, confidence, probabilities, top_features
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained yet. Call train() first.")

        X = self._build_features([text])
        proba = self.clf.predict_proba(X)[0]
        pred_idx = np.argmax(proba)
        pred_label = self.label_encoder.inverse_transform([pred_idx])[0]

        # Top class probabilities
        sorted_indices = np.argsort(proba)[::-1]
        probabilities = {
            self.label_encoder.inverse_transform([i])[0]: float(proba[i])
            for i in sorted_indices[:5]
        }

        # Feature importance for this prediction (approximate via feature values * global importance)
        top_features = self._get_top_features(X)

        return {
            "label": pred_label,
            "confidence": float(proba[pred_idx]),
            "probabilities": probabilities,
            "top_features": top_features,
        }

    def predict_batch(self, texts):
        """Predict for multiple logs at once."""
        return [self.predict(t) for t in texts]

    def _get_top_features(self, X, n=10):
        """Get top contributing features for a prediction."""
        importances = self.clf.feature_importances_

        # Get all feature names: TF-IDF vocab + structured
        tfidf_names = self.tfidf.get_feature_names_out().tolist()
        all_names = tfidf_names + self.feature_names

        # Multiply importance by feature value for this instance
        x_dense = X.toarray()[0]
        contributions = importances * np.abs(x_dense)

        top_indices = np.argsort(contributions)[::-1][:n]
        return [
            {"feature": all_names[i] if i < len(all_names) else f"feat_{i}",
             "importance": float(contributions[i]),
             "value": float(x_dense[i])}
            for i in top_indices
            if contributions[i] > 0
        ]

    def explain(self, text):
        """Generate SHAP-style explanation for a prediction.

        Returns the prediction plus feature contributions.
        Falls back to feature-importance-based explanation if shap fails.
        """
        prediction = self.predict(text)

        try:
            import shap

            X = self._build_features([text])
            explainer = shap.TreeExplainer(self.clf)
            shap_values = explainer.shap_values(X)

            tfidf_names = self.tfidf.get_feature_names_out().tolist()
            all_names = tfidf_names + self.feature_names

            pred_idx = list(self.label_encoder.classes_).index(prediction["label"])

            if isinstance(shap_values, list):
                sv = shap_values[pred_idx][0]
            else:
                sv = shap_values[0]

            abs_sv = np.abs(sv)
            top_indices = np.argsort(abs_sv)[::-1][:15]

            prediction["shap_explanation"] = [
                {
                    "feature": all_names[i] if i < len(all_names) else f"feat_{i}",
                    "shap_value": float(sv[i]),
                    "direction": "supports" if sv[i] > 0 else "opposes",
                }
                for i in top_indices
                if abs_sv[i] > 0.001
            ]
            prediction["explanation_method"] = "shap"

        except Exception:
            # SHAP fails on multi-class GradientBoosting — fall back to feature importance
            prediction["shap_explanation"] = prediction["top_features"]
            prediction["explanation_method"] = "feature_importance"

        return prediction

    def save(self, path):
        """Save trained model to disk."""
        if not self.is_trained:
            raise RuntimeError("Model not trained yet.")
        with open(path, "wb") as f:
            pickle.dump({
                "tfidf": self.tfidf,
                "clf": self.clf,
                "label_encoder": self.label_encoder,
                "feature_names": self.feature_names,
            }, f)

    def load(self, path):
        """Load a trained model from disk."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.tfidf = data["tfidf"]
        self.clf = data["clf"]
        self.label_encoder = data["label_encoder"]
        self.feature_names = data["feature_names"]
        self.is_trained = True
