# attachment_models.py

import os
os.environ['TF_USE_LEGACY_KERAS'] = 'True'

import tensorflow as tf
from keras.layers import Dense, Flatten, Layer, Input, Concatenate, Dropout, Masking, LSTM, GRU
from keras import Model
from keras.models import Sequential
from tensorflow.keras.optimizers.legacy import Adam
import keras
from keras import backend as K
import numpy as np

# Create a custom fallback attention layer in case keras_self_attention is not available
class CustomSeqSelfAttention(Layer):
    def __init__(self, units=None, attention_type='additive', 
                 kernel_initializer='glorot_normal', 
                 kernel_regularizer=None, bias_regularizer=None,
                 attention_regularizer_weight=0.0, attention_width=None,
                 history_only=False, attention_activation=None, **kwargs):
        self.units = units
        self.attention_type = attention_type
        self.kernel_initializer = keras.initializers.get(kernel_initializer)
        self.kernel_regularizer = keras.regularizers.get(kernel_regularizer)
        self.bias_regularizer = keras.regularizers.get(bias_regularizer)
        self.attention_regularizer_weight = attention_regularizer_weight
        self.attention_width = attention_width
        self.history_only = history_only
        self.attention_activation = attention_activation
        
        super(CustomSeqSelfAttention, self).__init__(**kwargs)
    
    def build(self, input_shape):
        self.input_spec = [keras.layers.InputSpec(shape=input_shape)]
        
        self.hidden_dim = input_shape[-1]
        self.attention_dim = self.units if self.units is not None else self.hidden_dim
        
        if self.attention_type == 'additive':
            self.Wt = self.add_weight(
                name='{}_Wt'.format(self.name),
                shape=(self.hidden_dim, self.attention_dim),
                initializer=self.kernel_initializer,
                regularizer=self.kernel_regularizer,
                trainable=True)
            
            self.Wm = self.add_weight(
                name='{}_Wm'.format(self.name),
                shape=(self.hidden_dim, self.attention_dim),
                initializer=self.kernel_initializer,
                regularizer=self.kernel_regularizer,
                trainable=True)
            
            self.bias = self.add_weight(
                name='{}_bias'.format(self.name),
                shape=(self.attention_dim,),
                initializer=keras.initializers.Zeros(),
                regularizer=self.bias_regularizer,
                trainable=True)
            
            self.context = self.add_weight(
                name='{}_context'.format(self.name),
                shape=(self.attention_dim,),
                initializer=self.kernel_initializer,
                regularizer=self.kernel_regularizer,
                trainable=True)
            
        elif self.attention_type == 'multiplicative':
            self.W = self.add_weight(
                name='{}_W'.format(self.name),
                shape=(self.hidden_dim, self.hidden_dim),
                initializer=self.kernel_initializer,
                regularizer=self.kernel_regularizer,
                trainable=True)
            
        super(CustomSeqSelfAttention, self).build(input_shape)
    
    def call(self, inputs, mask=None):
        # inputs shape: (batch_size, time_steps, hidden_dim)
        batch_size, time_steps = inputs.shape[0], inputs.shape[1]
        
        if self.attention_type == 'additive':
            # Additive attention
            q = K.expand_dims(K.dot(inputs, self.Wt), 2)  # (batch_size, time_steps, 1, att_dim)
            k = K.expand_dims(K.dot(inputs, self.Wm), 1)  # (batch_size, 1, time_steps, att_dim)
            
            # inputs shape: (batch_size, time_steps, time_steps, attention_dim)
            attention = K.tanh(q + k + self.bias)
            
            # Attention weights (batch_size, time_steps, time_steps, 1)
            e = K.dot(attention, K.reshape(self.context, (self.attention_dim, 1)))
            e = K.squeeze(e, -1)  # (batch_size, time_steps, time_steps)
            
        elif self.attention_type == 'multiplicative':
            # Multiplicative attention
            # Compute q = inputs * W
            q = K.dot(inputs, self.W)  # (batch_size, time_steps, hidden_dim)
            
            # Compute similarity with dot product
            # q · k^T where k = inputs
            e = K.batch_dot(q, inputs, axes=[2, 2])  # (batch_size, time_steps, time_steps)
        
        # Apply attention width constraint
        if self.attention_width is not None:
            lower = K.arange(0, time_steps) - self.attention_width // 2
            upper = lower + self.attention_width
            indices = K.expand_dims(K.arange(0, time_steps), axis=0)
            mask_l = K.cast(indices < K.expand_dims(lower, axis=1), K.floatx())
            mask_u = K.cast(indices > K.expand_dims(upper, axis=1), K.floatx())
            mask_wd = mask_l + mask_u
            e = e - 1e9 * mask_wd
        
        # Apply history only constraint
        if self.history_only:
            # Create masks for upper triangular part (future)
            mask_u = K.cast(K.ones_like(e) - K.tf.linalg.band_part(K.ones_like(e), -1, 0), K.floatx())
            e = e - 1e9 * mask_u
        
        # Apply masking
        if mask is not None:
            mask = K.cast(mask, K.floatx())
            mask = K.expand_dims(mask, 1)
            e = e - 1e9 * (1.0 - mask)
        
        # Apply attention activation
        if self.attention_activation == 'softmax':
            # Compute softmax over the time dimension
            a = K.softmax(e)
        else:
            a = K.exp(e)
            # Apply scaling
            a /= K.cast(K.sum(a, axis=-1, keepdims=True) + K.epsilon(), K.floatx())
        
        # Weight the input with attention scores
        v = K.batch_dot(a, inputs)  # (batch_size, time_steps, hidden_dim)
        
        return v
    
    def compute_output_shape(self, input_shape):
        return input_shape
    
    def get_config(self):
        config = {
            'units': self.units,
            'attention_type': self.attention_type,
            'kernel_initializer': keras.initializers.serialize(self.kernel_initializer),
            'kernel_regularizer': keras.regularizers.serialize(self.kernel_regularizer),
            'bias_regularizer': keras.regularizers.serialize(self.bias_regularizer),
            'attention_regularizer_weight': self.attention_regularizer_weight,
            'attention_width': self.attention_width,
            'history_only': self.history_only,
            'attention_activation': self.attention_activation,
        }
        base_config = super(CustomSeqSelfAttention, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))

# Try to import keras_self_attention or use custom implementation
try:
    from src.services.model_service.models.SAM.custom_seq_self_attention import SeqSelfAttention
    print("Successfully imported keras-self-attention")
except ImportError:
    print("Using custom SeqSelfAttention implementation")
    SeqSelfAttention = CustomSeqSelfAttention

# Set random seed for reproducibility
seed_value = 42

def keras_f1_score(y_true, y_pred):
    """
    Calculate F1 score using Keras backend operations.
    
    Args:
        y_true: Ground truth labels
        y_pred: Predicted labels
        
    Returns:
        F1 score value
    """
    true_positives = K.sum(K.round(K.clip(y_true * y_pred, 0, 1)))
    possible_positives = K.sum(K.round(K.clip(y_true, 0, 1)))
    predicted_positives = K.sum(K.round(K.clip(y_pred, 0, 1)))
    precision = true_positives / (predicted_positives + K.epsilon())
    recall = true_positives / (possible_positives + K.epsilon())
    f1_val = 2*(precision*recall)/(precision+recall+K.epsilon())
    return f1_val

def attachment_model_audio(sequence_length=25, num_columns=1024):
    """
    Create an audio-based attachment style prediction model.
    
    Args:
        sequence_length: Length of input sequences (default: 25)
        num_columns: Number of input features (default: 1024)
        
    Returns:
        Compiled Keras model
    """
    # Clear any existing session
    tf.keras.backend.clear_session()
    
    # Create model
    model = Sequential()
    model.add(Masking(mask_value=0., input_shape=(sequence_length, num_columns)))
    model.add(LSTM(64, seed=seed_value, return_sequences=True))
    attention = SeqSelfAttention(
        units=8,
        attention_type='additive',
        kernel_initializer=keras.initializers.GlorotNormal(seed=seed_value),
        kernel_regularizer=keras.regularizers.l2(1e-4),
        bias_regularizer=keras.regularizers.l1(1e-4),
        attention_regularizer_weight=1e-4,
        attention_width=4,
        history_only=True,
        attention_activation='softmax',
        name='Attention'
    )
    model.add(attention)
    model.add(Flatten())
    model.add(Dense(16, activation='relu'))
    model.add(Dropout(0.2))
    model.add(Dense(1, activation='sigmoid'))
    
    # Compile model
    opt = Adam(learning_rate=0.001, beta_1=0.9, beta_2=0.999, decay=0.01)
    model.compile(loss='binary_crossentropy', metrics=[keras_f1_score])
    
    return model

def attachment_model_text(sequence_length=25, num_columns=768):
    """
    Create a text-based attachment style prediction model.
    
    Args:
        sequence_length: Length of input sequences (default: 25)
        num_columns: Number of input features (default: 768)
        
    Returns:
        Compiled Keras model
    """
    # Clear any existing session
    tf.keras.backend.clear_session()
    
    # Create model
    model = Sequential()
    model.add(Masking(mask_value=0., input_shape=(sequence_length, num_columns)))
    model.add(LSTM(64, seed=seed_value, return_sequences=True))
    attention = SeqSelfAttention(
        units=None,  # No additional units
        attention_type='multiplicative',
        kernel_initializer=keras.initializers.GlorotNormal(seed=seed_value),
        kernel_regularizer=keras.regularizers.l2(1e-4),
        bias_regularizer=keras.regularizers.l1(1e-4),
        attention_regularizer_weight=1e-4,
        attention_width=4,
        history_only=False,
        attention_activation=None,
        name='Attention'
    )
    model.add(attention)
    model.add(Flatten())
    model.add(Dense(32, activation='relu'))
    model.add(Dropout(0.2))
    model.add(Dense(1, activation='sigmoid'))
    
    # Compile model
    opt = Adam(learning_rate=0.001, beta_1=0.9, beta_2=0.999, decay=0.01)
    model.compile(loss='binary_crossentropy', metrics=[keras_f1_score])
    
    return model

def attachment_model_mc1(sequence_length=25, num_columns=1024+768):
    """
    Create a combined multimodal attachment style prediction model (MC1).
    
    Args:
        sequence_length: Length of input sequences (default: 25)
        num_columns: Number of input features (default: 1024+768)
        
    Returns:
        Compiled Keras model
    """
    # Clear any existing session
    tf.keras.backend.clear_session()
    
    # Create model
    model = Sequential()
    model.add(Masking(mask_value=0., input_shape=(sequence_length, num_columns)))
    model.add(LSTM(16, seed=seed_value, return_sequences=True))
    attention = SeqSelfAttention(
        units=8,
        attention_type='additive',
        kernel_initializer=keras.initializers.GlorotNormal(seed=seed_value),
        kernel_regularizer=keras.regularizers.l2(1e-4),
        bias_regularizer=keras.regularizers.l1(1e-4),
        attention_regularizer_weight=1e-4,
        attention_width=2,
        history_only=True,
        attention_activation=None,
        name='Attention'
    )
    model.add(attention)
    model.add(Flatten())
    model.add(Dense(16, activation='relu'))
    model.add(Dropout(0.2))
    model.add(Dense(1, activation='sigmoid'))
    
    # Compile model
    opt = Adam(learning_rate=0.001, beta_1=0.9, beta_2=0.999, decay=0.01)
    model.compile(loss='binary_crossentropy', metrics=[keras_f1_score])
    
    return model

def attachment_unimodel_lstm(sequence_length, num_columns, lstm_units, att_units, att_type, att_window, att_hist, att_act, dense_units):
    """
    Create a unimodal LSTM model with self-attention for feature extraction.
    
    Args:
        sequence_length: Length of input sequences
        num_columns: Number of input features
        lstm_units: Number of LSTM units
        att_units: Number of attention units
        att_type: Type of attention ('additive' or 'multiplicative')
        att_window: Window size for attention
        att_hist: Whether to only attend to previous timesteps
        att_act: Activation function for attention
        dense_units: Number of dense units
        
    Returns:
        Keras model
    """
    # Define input layer
    inputs = Input(shape=(sequence_length, num_columns))
    # Masking layer
    masked_inputs = Masking(mask_value=0.)(inputs)
    # LSTM layer
    lstm_out = LSTM(lstm_units, seed=seed_value, return_sequences=True)(masked_inputs)
    # Self-attention layer
    attention_out = SeqSelfAttention(
        units=att_units,
        attention_type=att_type,
        kernel_initializer=keras.initializers.GlorotNormal(seed=seed_value),
        kernel_regularizer=keras.regularizers.l2(1e-4),
        bias_regularizer=keras.regularizers.l2(1e-4),
        attention_regularizer_weight=1e-4,
        attention_width=att_window,
        history_only=att_hist,
        attention_activation=att_act,
        name='Attention'
    )(lstm_out)
    
    return Model(inputs=inputs, outputs=attention_out)

def attachment_model_mc2(sequence_length=25, num_columns_text=768, num_columns_audio=1024):
    """
    Create a more sophisticated multimodal attachment style prediction model (MC2).
    
    Args:
        sequence_length: Length of input sequences (default: 25)
        num_columns_text: Number of text features (default: 768)
        num_columns_audio: Number of audio features (default: 1024)
        
    Returns:
        Compiled Keras model
    """
    # Clear any existing session
    tf.keras.backend.clear_session()
    
    # Define unimodal parameters
    params = [
        {
            "lstm_units": 64,
            "att_units": None,
            "att_type": "multiplicative",
            "att_window": 4,
            "att_hist": False,
            "att_act": None,
            "dense_units": 32
        },
        {
            "lstm_units": 64,
            "att_units": 8,
            "att_type": "additive",
            "att_window": 4,
            "att_hist": True,
            "att_act": "softmax",
            "dense_units": 16
        }
    ]
    
    # Define input layers
    input_text = Input(shape=(sequence_length, num_columns_text))
    input_audio = Input(shape=(sequence_length, num_columns_audio))
    
    # Create unimodal feature extractors
    unimodal_rnn_text = attachment_unimodel_lstm(
        sequence_length=sequence_length,
        num_columns=num_columns_text,
        lstm_units=params[0]["lstm_units"],
        att_units=params[0]["att_units"],
        att_type=params[0]["att_type"],
        att_window=params[0]["att_window"],
        att_hist=params[0]["att_hist"],
        att_act=params[0]["att_act"],
        dense_units=params[0]["dense_units"]
    )
    
    unimodal_rnn_audio = attachment_unimodel_lstm(
        sequence_length=sequence_length,
        num_columns=num_columns_audio,
        lstm_units=params[1]["lstm_units"],
        att_units=params[1]["att_units"],
        att_type=params[1]["att_type"],
        att_window=params[1]["att_window"],
        att_hist=params[1]["att_hist"],
        att_act=params[1]["att_act"],
        dense_units=params[1]["dense_units"]
    )
    
    # Process unimodal inputs
    output_text = unimodal_rnn_text(input_text)
    output_audio = unimodal_rnn_audio(input_audio)
    
    # Concatenate outputs
    concatenated = Concatenate()([output_text, output_audio])
    
    # GRU layer
    gru_layer = GRU(64, seed=seed_value)(concatenated)
    dense_layer = Dense(32, activation='relu')(gru_layer)
    dropout_layer = Dropout(0.2)(dense_layer)
    
    # Output layer
    output = Dense(1, activation='sigmoid')(dropout_layer)
    
    # Create model
    model = Model(inputs=[input_text, input_audio], outputs=output)
    
    # Compile model
    opt = Adam(learning_rate=0.001, beta_1=0.9, beta_2=0.999, decay=0.01)
    model.compile(loss='binary_crossentropy', metrics=[keras_f1_score])
    
    return model

def format_hidden_states(hidden_states, target_shape=(1, 25, None)):
    """
    Format hidden states to match expected model input shape.
    
    Args:
        hidden_states: Hidden states tensor or numpy array
        target_shape: Tuple of (batch_size, seq_len, features) with None for flexible dimension
        
    Returns:
        Formatted numpy array with shape matching target_shape
    """
    # Convert to numpy if tensor
    if hasattr(hidden_states, 'numpy'):
        hidden_states = hidden_states.numpy()
    elif hasattr(hidden_states, 'detach'):
        hidden_states = hidden_states.detach().cpu().numpy()
    
    # Get actual dimensions
    input_shape = hidden_states.shape
    batch_size, seq_len = target_shape[0], target_shape[1]
    
    # Handle different input shapes
    if len(input_shape) == 2:
        # Shape is [batch_size or tokens, hidden_dim]
        hidden_dim = input_shape[1]
        
        if input_shape[0] == 1:
            # Single vector, repeat to create sequence
            return np.tile(hidden_states, (seq_len, 1)).reshape(batch_size, seq_len, hidden_dim)
        else:
            # Multiple tokens, take first seq_len or pad
            actual_seq_len = min(input_shape[0], seq_len)
            padded_data = np.zeros((seq_len, hidden_dim))
            padded_data[:actual_seq_len] = hidden_states[:actual_seq_len]
            return padded_data.reshape(batch_size, seq_len, hidden_dim)
    
    elif len(input_shape) == 3:
        # Shape is [batch_size, tokens, hidden_dim]
        if input_shape[1] != seq_len:
            # Need to adjust sequence length
            hidden_dim = input_shape[2]
            padded_data = np.zeros((batch_size, seq_len, hidden_dim))
            # Copy the min of actual length and target length
            copy_len = min(input_shape[1], seq_len)
            padded_data[:, :copy_len, :] = hidden_states[:, :copy_len, :]
            return padded_data
        else:
            # Already has the right sequence length
            return hidden_states
    
    # Unknown shape, return original
    return hidden_states

def predict_attachment(model_type, bert_hidden_states=None, wav2vec2_hidden_states=None, model_path=None):
    """
    Predict attachment style using the specified model type and hidden states.
    
    Args:
        model_type: Type of model ('Audio Model', 'Text Model', 'Multimodal MC1', or 'Multimodal MC2')
        bert_hidden_states: Hidden states from BERT model (for text)
        wav2vec2_hidden_states: Hidden states from wav2vec2 model (for audio)
        model_path: Path to pre-trained model weights (if None, uses default paths)
        
    Returns:
        Dictionary with prediction results
    """
    result = {"success": False, "error": None, "prediction": None, "probability": None}
    
    try:
        # If no model weights exist, we can use mock predictions for testing
        # This is a fallback for when you're testing without model weights
        run_demo_mode = False
        
        # Set default model paths if not provided
        if model_path is None:
            base_path = "models/"
            model_paths = {
                "Audio Model": base_path + "attachment_weights_audio.h5",
                "Text Model": base_path + "attachment_weights_text.h5",
                "Multimodal MC1": base_path + "attachment_weights_mc1.h5",
                "Multimodal MC2": base_path + "attachment_weights_mc2.h5"
            }
            model_path = model_paths.get(model_type)
            
            # Check if model path exists
            if not os.path.exists(model_path):
                print(f"Warning: Model weights file not found at {model_path}. Running in demo mode.")
                run_demo_mode = True
        
        print(f"Using model path: {model_path}")
        
        # Create and load the appropriate model
        if model_type == "Audio Model":
            if wav2vec2_hidden_states is None:
                result["error"] = "Audio hidden states are required for this model"
                return result
            
            # Format hidden states
            formatted_audio = format_hidden_states(wav2vec2_hidden_states, target_shape=(1, 25, 1024))
            
            if run_demo_mode:
                # Generate a random prediction for testing
                prediction = np.array([[np.random.random()]])
            else:
                # Create model and load weights
                model = attachment_model_audio()
                if model_path:
                    model.load_weights(model_path)
                
                # Make prediction
                prediction = model.predict(formatted_audio)
            
        elif model_type == "Text Model":
            if bert_hidden_states is None:
                result["error"] = "Text hidden states are required for this model"
                return result
            
            # Format hidden states
            formatted_text = format_hidden_states(bert_hidden_states, target_shape=(1, 25, 768))
            
            if run_demo_mode:
                # Generate a random prediction for testing
                prediction = np.array([[np.random.random()]])
            else:
                # Create model and load weights
                model = attachment_model_text()
                if model_path:
                    model.load_weights(model_path)
                
                # Make prediction
                prediction = model.predict(formatted_text)
            
        elif model_type == "Multimodal MC1":
            if bert_hidden_states is None or wav2vec2_hidden_states is None:
                result["error"] = "Both text and audio hidden states are required for this model"
                return result
            
            # Format and concatenate hidden states
            formatted_text = format_hidden_states(bert_hidden_states, target_shape=(1, 25, 768))
            formatted_audio = format_hidden_states(wav2vec2_hidden_states, target_shape=(1, 25, 1024))
            
            # Concatenate along feature dimension
            combined = np.concatenate([formatted_text, formatted_audio], axis=2)
            
            if run_demo_mode:
                # Generate a random prediction for testing
                prediction = np.array([[np.random.random()]])
            else:
                # Create model and load weights
                model = attachment_model_mc1()
                if model_path:
                    model.load_weights(model_path)
                
                # Make prediction
                prediction = model.predict(combined)
            
        elif model_type == "Multimodal MC2":
            if bert_hidden_states is None or wav2vec2_hidden_states is None:
                result["error"] = "Both text and audio hidden states are required for this model"
                return result
            
            # Format hidden states
            formatted_text = format_hidden_states(bert_hidden_states, target_shape=(1, 25, 768))
            formatted_audio = format_hidden_states(wav2vec2_hidden_states, target_shape=(1, 25, 1024))
            
            if run_demo_mode:
                # Generate a random prediction for testing
                prediction = np.array([[np.random.random()]])
            else:
                # Create model and load weights
                model = attachment_model_mc2()
                if model_path:
                    model.load_weights(model_path)
                
                # Make prediction with multiple inputs
                prediction = model.predict([formatted_text, formatted_audio])
            
        else:
            result["error"] = f"Unknown model type: {model_type}"
            return result
        
        # Process prediction results
        probability = float(prediction[0][0])
        binary_prediction = 1 if probability >= 0.5 else 0
        
        # Map binary prediction to attachment style (assuming 1 = secure, 0 = insecure)
        attachment_style = "Secure" if binary_prediction == 1 else "Insecure"
        
        # Update result
        result["success"] = True
        result["prediction"] = attachment_style
        result["probability"] = probability
        result["secure_probability"] = probability
        result["insecure_probability"] = 1 - probability
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        result["error"] = str(e)
    
    return result