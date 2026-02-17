import litserve as ls
from starlette.middleware.cors import CORSMiddleware

# Available English projects from Finto AI
AVAILABLE_PROJECTS = {
    "yso-en": {
        "name": "YSO English (2025.2.Kant)",
        "language": "en",
        "backend": "nn_ensemble"
    },
    "ykl-en": {
        "name": "PLC English",
        "language": "en",
        "backend": "ensemble"
    }
}

class AnnifAPI(ls.LitAPI):
    def setup(self, device):
        """Set up ANNIF predictor using Finto AI API"""
        from src.services.model_service.models.ANNIF.annif_predictor import AnnifPredictor
        self.model = AnnifPredictor(
            base_url="https://ai.finto.fi/v1",
            available_projects=AVAILABLE_PROJECTS
        )

    def decode_request(self, request):
        """Convert the request payload to model input"""
        text = request.get("text", "")
        documents = request.get("documents", None)  # For batch requests
        project_id = request.get("project_id", "yso-en")  # Default to yso-en
        limit = request.get("limit", 10)
        threshold = request.get("threshold", 0.0)

        # Determine if batch or single
        is_batch = documents is not None

        return text, documents, project_id, limit, threshold, is_batch

    def predict(self, inputs):
        """Predict subjects/topics for single or batch documents"""
        text, documents, project_id, limit, threshold, is_batch = inputs

        if is_batch:
            return self.model.predict_batch(documents, project_id, limit, threshold)
        else:
            return self.model.predict(text, project_id, limit, threshold)

    def encode_response(self, output):
        """Convert the model output to a response payload"""
        return {"output": output}

def run_annif_api():
    import os, sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent.parent.parent.parent
    sys.path.insert(0, str(project_root))

    api = AnnifAPI()
    cors_middleware = (
        CORSMiddleware,
        {
            "allow_origins": ["*"],
            "allow_methods": ["GET", "POST"],
            "allow_headers": ["*"],
        }
    )
    server = ls.LitServer(
        api,
        middlewares=[cors_middleware],
        workers_per_device=1
    )
    server.run(
        port=8004,
        generate_client_file=False
    )

if __name__ == "__main__":
    run_annif_api()
