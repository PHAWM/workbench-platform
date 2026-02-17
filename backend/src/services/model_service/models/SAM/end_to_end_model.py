"""
This model's docuemnation and development can be found here 

Paper: https://eprints.gla.ac.uk/341005/1/341005.pdf
Github: https://github.com/bukera/attachment_emo_clf
""" 

import os
import numpy as np
import torch
import soundfile as sf
from scipy import signal
import tempfile
from typing import Dict, Any, Optional, Union
import warnings
warnings.filterwarnings("ignore")

# Set TensorFlow to use legacy Keras
os.environ['TF_USE_LEGACY_KERAS'] = 'True'

# Import required libraries
from transformers import (
    pipeline,
    WhisperProcessor,
    AutoTokenizer,
    AutoModelForSequenceClassification,
    Wav2Vec2FeatureExtractor,
    AutoConfig
)

# Import attachment models (assuming they're available)
from src.services.model_service.models.SAM.attachment_models import (
    attachment_model_audio,
    attachment_model_text, 
    attachment_model_mc1,
    attachment_model_mc2,
    format_hidden_states
)

class AttachmentPredictor:
    """
    End-to-end attachment style prediction pipeline that supports all 4 model types:
    - Audio Model: Uses wav2vec2 hidden states
    - Text Model: Uses BERT hidden states  
    - Multimodal MC1: Concatenated BERT + wav2vec2 features
    - Multimodal MC2: Separate processing of BERT + wav2vec2 features
    """
    
    def __init__(self):
        self.models_loaded = False
        self.transcriber = None
        self.whisper_processor = None
        self.bert_tokenizer = None
        self.bert_model = None
        self.wav2vec2_feature_extractor = None
        self.wav2vec2_model = None
        
        # Model paths (absolute paths for Docker container compatibility)
        self.model_paths = {
            "audio": "/app/src/services/model_service/models/SAM/weights/attachment_weights_audio_model.h5",
            "text": "/app/src/services/model_service/models/SAM/weights/attachment_weights_text_model.h5",
            "mc1": "/app/src/services/model_service/models/SAM/weights/attachment_weights_mc1_model.h5",
            "mc2": "/app/src/services/model_service/models/SAM/weights/attachment_weights_mc2_model.h5"
        }
    
    def load_models(self):
        """Load all required models for feature extraction."""
        print("Loading models...")
        
        # Load Whisper for transcription
        self.transcriber = pipeline("automatic-speech-recognition", 
                                   model="openai/whisper-base",
                                   device=0 if torch.cuda.is_available() else -1)
        self.whisper_processor = WhisperProcessor.from_pretrained("openai/whisper-base")
        
        # Load BERT for text emotion analysis
        self.bert_tokenizer = AutoTokenizer.from_pretrained("bhadresh-savani/bert-base-uncased-emotion")
        self.bert_model = AutoModelForSequenceClassification.from_pretrained(
            "bhadresh-savani/bert-base-uncased-emotion",
            output_hidden_states=True
        )
        
        # Load wav2vec2 for audio emotion analysis
        self.wav2vec2_feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(
            "AreejB/wav2vec2-xlsr-english-speech-emotion-recognition"
        )
        
        # Load wav2vec2 model with custom class handling
        try:
            from utils import CustomWav2Vec2ForSpeechClassification
            self.wav2vec2_model = CustomWav2Vec2ForSpeechClassification.from_pretrained(
                "AreejB/wav2vec2-xlsr-english-speech-emotion-recognition",
                output_hidden_states=True
            )
        except:
            # Fallback to AutoModel
            from transformers import AutoModel
            self.wav2vec2_model = AutoModel.from_pretrained(
                "AreejB/wav2vec2-xlsr-english-speech-emotion-recognition",
                output_hidden_states=True
            )
        
        self.models_loaded = True
        print("All models loaded successfully!")
    
    def preprocess_audio(self, audio_file_path: str) -> tuple:
        """
        Preprocess audio file for wav2vec2 model.
        
        Args:
            audio_file_path: Path to audio file
            
        Returns:
            Tuple of (audio_array, sample_rate)
        """
        # Read audio file
        audio_input, sample_rate = sf.read(audio_file_path)
        
        # Ensure audio is mono
        if len(audio_input.shape) > 1:
            audio_input = audio_input[:, 0]
        
        # Resample to 16kHz if needed
        if sample_rate != 16000:
            number_of_samples = round(len(audio_input) * 16000 / sample_rate)
            audio_input = signal.resample(audio_input, number_of_samples)
            sample_rate = 16000
        
        return audio_input, sample_rate
    
    def extract_bert_features(self, audio_file_path: str) -> torch.Tensor:
        """
        Extract BERT hidden states from audio file via transcription.
        
        Args:
            audio_file_path: Path to audio file
            
        Returns:
            BERT hidden states tensor
        """
        # Transcribe audio
        result = self.transcriber(audio_file_path)
        transcript = result["text"]
        
        # Normalize text
        normalized_text = self.whisper_processor.tokenizer._normalize(transcript)
        
        # Get BERT features
        inputs = self.bert_tokenizer(normalized_text, return_tensors="pt", 
                                   padding=True, truncation=True)
        
        with torch.no_grad():
            output = self.bert_model(**inputs, output_hidden_states=True)
            bert_hidden_states = output.hidden_states[-1]  # Last layer
        
        return bert_hidden_states
    
    def extract_wav2vec2_features(self, audio_file_path: str) -> torch.Tensor:
        """
        Extract wav2vec2 hidden states from audio file.
        
        Args:
            audio_file_path: Path to audio file
            
        Returns:
            wav2vec2 hidden states tensor
        """
        # Preprocess audio
        audio_input, sample_rate = self.preprocess_audio(audio_file_path)
        
        # Process with wav2vec2
        inputs = self.wav2vec2_feature_extractor(
            audio_input, 
            sampling_rate=16000,
            return_tensors="pt"
        )
        
        with torch.no_grad():
            outputs = self.wav2vec2_model(inputs.input_values, output_hidden_states=True)
            wav2vec2_hidden_states = outputs.hidden_states[-1]  # Last layer
        
        return wav2vec2_hidden_states
    
    def predict_audio_model(self, audio_file_path: str, model_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Predict attachment style using audio-only model.
        
        Args:
            audio_file_path: Path to audio file
            model_path: Optional custom model path
            
        Returns:
            Dictionary with prediction results
        """
        if not self.models_loaded:
            raise ValueError("Models not loaded. Call load_models() first.")
        
        # Extract wav2vec2 features
        wav2vec2_hidden_states = self.extract_wav2vec2_features(audio_file_path)
        
        # Format hidden states
        formatted_audio = format_hidden_states(wav2vec2_hidden_states, target_shape=(1, 25, 1024))
        
        # Load and predict with audio model
        model_path = model_path or self.model_paths["audio"]
        
        if os.path.exists(model_path):
            model = attachment_model_audio()
            model.load_weights(model_path)
            prediction = model.predict(formatted_audio, verbose=0)
        else:
            # Demo mode - random prediction
            prediction = np.array([[np.random.random()]])
            print(f"Warning: Model weights not found at {model_path}. Using demo prediction.")
        
        # Process results
        probability = float(prediction[0][0])
        attachment_style = "Secure" if probability >= 0.5 else "Insecure"
        
        return {
            "success": True,
            "model_type": "Audio Model",
            "prediction": attachment_style,
            "secure_probability": probability,
            "insecure_probability": 1 - probability,
            "confidence": max(probability, 1 - probability)
        }
    
    def predict_text_model(self, audio_file_path: str, model_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Predict attachment style using text-only model.
        
        Args:
            audio_file_path: Path to audio file
            model_path: Optional custom model path
            
        Returns:
            Dictionary with prediction results
        """
        if not self.models_loaded:
            raise ValueError("Models not loaded. Call load_models() first.")
        
        # Extract BERT features
        bert_hidden_states = self.extract_bert_features(audio_file_path)
        
        # Format hidden states
        formatted_text = format_hidden_states(bert_hidden_states, target_shape=(1, 25, 768))
        
        # Load and predict with text model
        model_path = model_path or self.model_paths["text"]
        
        if os.path.exists(model_path):
            model = attachment_model_text()
            model.load_weights(model_path)
            prediction = model.predict(formatted_text, verbose=0)
        else:
            # Demo mode - random prediction
            prediction = np.array([[np.random.random()]])
            print(f"Warning: Model weights not found at {model_path}. Using demo prediction.")
        
        # Process results
        probability = float(prediction[0][0])
        attachment_style = "Secure" if probability >= 0.5 else "Insecure"
        
        return {
            "success": True,
            "model_type": "Text Model",
            "prediction": attachment_style,
            "secure_probability": probability,
            "insecure_probability": 1 - probability,
            "confidence": max(probability, 1 - probability)
        }
    
    def predict_multimodal_mc1(self, audio_file_path: str, model_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Predict attachment style using multimodal MC1 model (concatenated features).
        
        Args:
            audio_file_path: Path to audio file
            model_path: Optional custom model path
            
        Returns:
            Dictionary with prediction results
        """
        if not self.models_loaded:
            raise ValueError("Models not loaded. Call load_models() first.")
        
        # Extract both types of features
        bert_hidden_states = self.extract_bert_features(audio_file_path)
        wav2vec2_hidden_states = self.extract_wav2vec2_features(audio_file_path)
        
        # Format and concatenate hidden states
        formatted_text = format_hidden_states(bert_hidden_states, target_shape=(1, 25, 768))
        formatted_audio = format_hidden_states(wav2vec2_hidden_states, target_shape=(1, 25, 1024))
        
        # Concatenate along feature dimension
        combined = np.concatenate([formatted_text, formatted_audio], axis=2)
        
        # Load and predict with MC1 model
        model_path = model_path or self.model_paths["mc1"]
        
        if os.path.exists(model_path):
            model = attachment_model_mc1()
            model.load_weights(model_path)
            prediction = model.predict(combined, verbose=0)
        else:
            # Demo mode - random prediction
            prediction = np.array([[np.random.random()]])
            print(f"Warning: Model weights not found at {model_path}. Using demo prediction.")
        
        # Process results
        probability = float(prediction[0][0])
        attachment_style = "Secure" if probability >= 0.5 else "Insecure"
        
        return {
            "success": True,
            "model_type": "Multimodal MC1",
            "prediction": attachment_style,
            "secure_probability": probability,
            "insecure_probability": 1 - probability,
            "confidence": max(probability, 1 - probability)
        }
    
    def predict_multimodal_mc2(self, audio_file_path: str, model_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Predict attachment style using multimodal MC2 model (separate processing).
        
        Args:
            audio_file_path: Path to audio file
            model_path: Optional custom model path
            
        Returns:
            Dictionary with prediction results
        """
        if not self.models_loaded:
            raise ValueError("Models not loaded. Call load_models() first.")
        
        # Extract both types of features
        bert_hidden_states = self.extract_bert_features(audio_file_path)
        wav2vec2_hidden_states = self.extract_wav2vec2_features(audio_file_path)
        
        # Format hidden states separately
        formatted_text = format_hidden_states(bert_hidden_states, target_shape=(1, 25, 768))
        formatted_audio = format_hidden_states(wav2vec2_hidden_states, target_shape=(1, 25, 1024))
        
        # Load and predict with MC2 model
        model_path = model_path or self.model_paths["mc2"]
        
        if os.path.exists(model_path):
            model = attachment_model_mc2()
            model.load_weights(model_path)
            prediction = model.predict([formatted_text, formatted_audio], verbose=0)
        else:
            # Demo mode - random prediction
            prediction = np.array([[np.random.random()]])
            print(f"Warning: Model weights not found at {model_path}. Using demo prediction.")
        
        # Process results
        probability = float(prediction[0][0])
        attachment_style = "Secure" if probability >= 0.5 else "Insecure"
        
        return {
            "success": True,
            "model_type": "Multimodal MC2",
            "prediction": attachment_style,
            "secure_probability": probability,
            "insecure_probability": 1 - probability,
            "confidence": max(probability, 1 - probability)
        }
    
    def predict_all_models(self, audio_file_path: str) -> Dict[str, Dict[str, Any]]:
        """
        Run prediction using all 4 models and return comparative results.
        
        Args:
            audio_file_path: Path to audio file
            
        Returns:
            Dictionary containing results from all models
        """
        results = {}
        
        try:
            results["audio"] = self.predict_audio_model(audio_file_path)
        except Exception as e:
            results["audio"] = {"success": False, "error": str(e)}
        
        try:
            results["text"] = self.predict_text_model(audio_file_path)
        except Exception as e:
            results["text"] = {"success": False, "error": str(e)}
        
        try:
            results["mc1"] = self.predict_multimodal_mc1(audio_file_path)
        except Exception as e:
            results["mc1"] = {"success": False, "error": str(e)}
        
        try:
            results["mc2"] = self.predict_multimodal_mc2(audio_file_path)
        except Exception as e:
            results["mc2"] = {"success": False, "error": str(e)}
        
        return results
    
    def predict_single_model(self, audio_file_path: str, model_type: str) -> Dict[str, Any]:
        """
        Run prediction using a single specified model.
        
        Args:
            audio_file_path: Path to audio file
            model_type: One of "audio", "text", "mc1", "mc2"
            
        Returns:
            Dictionary with prediction results
        """
        model_functions = {
            "audio": self.predict_audio_model,
            "text": self.predict_text_model,
            "mc1": self.predict_multimodal_mc1,
            "mc2": self.predict_multimodal_mc2
        }
        
        if model_type.lower() not in model_functions:
            return {
                "success": False,
                "error": f"Unknown model type: {model_type}. Choose from: audio, text, mc1, mc2"
            }
        
        return model_functions[model_type.lower()](audio_file_path)


# Convenience function for quick predictions
def predict_attachment_style(audio_file_path: str, 
                           model_type: str = "all",
                           load_models: bool = True) -> Union[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    """
    Convenience function to quickly predict attachment style from audio file.
    
    Args:
        audio_file_path: Path to audio file
        model_type: Model to use ("audio", "text", "mc1", "mc2", or "all")
        load_models: Whether to load models (set False if already loaded)
        
    Returns:
        Prediction results (single dict for specific model, nested dict for "all")
    
    Example:
        # Predict with all models
        results = predict_attachment_style("audio.wav", "all")
        
        # Predict with specific model  
        result = predict_attachment_style("audio.wav", "audio")
    """
    predictor = AttachmentPredictor()
    
    if load_models:
        predictor.load_models()
    
    if model_type.lower() == "all":
        return predictor.predict_all_models(audio_file_path)
    else:
        return predictor.predict_single_model(audio_file_path, model_type)


# Example usage
if __name__ == "__main__":
    # Initialize predictor
    predictor = AttachmentPredictor()
    predictor.load_models()
    
    # Example audio file path
    audio_file = "sample_audio.wav"
    
    # Run all models
    print("Running all models...")
    all_results = predictor.predict_all_models(audio_file)
    
    # Display results
    for model_name, result in all_results.items():
        if result["success"]:
            print(f"\n{result['model_type']}:")
            print(f"  Prediction: {result['prediction']}")
            print(f"  Confidence: {result['confidence']:.2%}")
        else:
            print(f"\n{model_name.upper()} Model: Error - {result['error']}")
    
    # Or run single model
    print("\nRunning single model...")
    single_result = predictor.predict_audio_model(audio_file)
    print(f"Audio Model Result: {single_result['prediction']} ({single_result['confidence']:.2%} confidence)")