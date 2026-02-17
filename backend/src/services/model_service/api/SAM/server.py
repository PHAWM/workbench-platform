import litserve as ls

from starlette.middleware.cors import CORSMiddleware

class SchoolAttachmentMonitorAPI(ls.LitAPI):
    def setup(self, device):
        from src.services.model_service.models.SAM import AttachmentPredictor
        """Set up the model, so it can be called in `predict`"""
        self.model = AttachmentPredictor()
        self.model.load_models()

    def decode_request(self, request):
        """Convert the request payload to your model input."""
        return request["file_location"], request["model_type"]

    def predict(self, inputs):
        """Predict the output

        Args:
            file_location (dict): a dictionary which includes audit_id and file name such as {"audit_id":audit_id, "file_name":file_name}
            model_type (str): one of the options ["audio", "text", "mc1", "mc2", "all"], if the model_type is none then it will return all the 

        Returns:
            dict: {
                "success": True,
                "model_type": "Audio Model" or "Text Model or "Multimodal MC1" or "Multimodal MC2",
                "prediction": attachment_style,
                "secure_probability": probability,
                "insecure_probability": 1 - probability,
                "confidence": max(probability, 1 - probability)
            }
        """
        file_location, model_type = inputs
        audio_file_path = file_location
        if model_type == "all" or not model_type:
            return self.model.predict_all_models(audio_file_path)
        else:
            return self.model.predict_single_model(audio_file_path, model_type)

    def encode_response(self, output):
        """Convert the model output to a response payload"""
        return {"output": output}
    
def run_sam_api():
    import os, sys
    from pathlib import Path
     
    # parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = Path(__file__).parent.parent.parent.parent.parent.parent
    sys.path.insert(0, str(project_root))
    
    api = SchoolAttachmentMonitorAPI()
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
        port=8002,
        generate_client_file=False
    )
    
if __name__ == "__main__":
    run_sam_api()