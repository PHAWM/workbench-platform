import tensorflow as tf
from keras.layers import Layer
import keras

class SeqSelfAttention(Layer):
    """
    Custom implementation of Sequential Self-Attention mechanism compatible with newer Keras versions.
    Based on the original keras-self-attention package but updated to avoid backend compatibility issues.
    """

    ATTENTION_TYPE_ADD = 'additive'
    ATTENTION_TYPE_MUL = 'multiplicative'

    def __init__(self,
                 units=32,
                 attention_width=None,
                 attention_type='additive',
                 return_attention=False,
                 history_only=False,
                 kernel_initializer='glorot_normal',
                 bias_initializer='zeros',
                 kernel_regularizer=None,
                 bias_regularizer=None,
                 kernel_constraint=None,
                 bias_constraint=None,
                 use_additive_bias=True,
                 use_attention_bias=True,
                 attention_activation=None,
                 attention_regularizer_weight=0.0,
                 **kwargs):
        """Layer initialization.

        For additive attention, see: https://arxiv.org/pdf/1806.01264.pdf

        :param units: The dimension of the vectors that used to calculate the attention weights.
        :param attention_width: The width of local attention.
        :param attention_type: 'additive' or 'multiplicative'.
        :param return_attention: Whether to return the attention weights for visualization.
        :param history_only: Only use historical pieces of data.
        :param kernel_initializer: The initializer for weight matrices.
        :param bias_initializer: The initializer for biases.
        :param kernel_regularizer: The regularization for weight matrices.
        :param bias_regularizer: The regularization for biases.
        :param kernel_constraint: The constraint for weight matrices.
        :param bias_constraint: The constraint for biases.
        :param use_additive_bias: Whether to use bias while calculating the relevance of inputs features
                                  in additive mode.
        :param use_attention_bias: Whether to use bias while calculating the weights of attention.
        :param attention_activation: The activation used for calculating the weights of attention.
        :param attention_regularizer_weight: The weights of attention regularizer.
        :param kwargs: Parameters for parent class.
        """
        super(SeqSelfAttention, self).__init__(**kwargs)
        self.supports_masking = True
        self.units = units
        self.attention_width = attention_width
        self.attention_type = attention_type
        self.return_attention = return_attention
        self.history_only = history_only
        if history_only and attention_width is None:
            self.attention_width = int(1e9)

        self.use_additive_bias = use_additive_bias
        self.use_attention_bias = use_attention_bias
        self.kernel_initializer = keras.initializers.get(kernel_initializer)
        self.bias_initializer = keras.initializers.get(bias_initializer)
        self.kernel_regularizer = keras.regularizers.get(kernel_regularizer)
        self.bias_regularizer = keras.regularizers.get(bias_regularizer)
        self.kernel_constraint = keras.constraints.get(kernel_constraint)
        self.bias_constraint = keras.constraints.get(bias_constraint)
        self.attention_activation = keras.activations.get(attention_activation)
        self.attention_regularizer_weight = attention_regularizer_weight

        if attention_type == SeqSelfAttention.ATTENTION_TYPE_ADD:
            self.Wx, self.Wt, self.bh = None, None, None
            self.Wa, self.ba = None, None
        elif attention_type == SeqSelfAttention.ATTENTION_TYPE_MUL:
            self.Wa, self.ba = None, None
        else:
            raise NotImplementedError('No implementation for attention type : ' + attention_type)

    def get_config(self):
        config = {
            'units': self.units,
            'attention_width': self.attention_width,
            'attention_type': self.attention_type,
            'return_attention': self.return_attention,
            'history_only': self.history_only,
            'use_additive_bias': self.use_additive_bias,
            'use_attention_bias': self.use_attention_bias,
            'kernel_initializer': keras.initializers.serialize(self.kernel_initializer),
            'bias_initializer': keras.initializers.serialize(self.bias_initializer),
            'kernel_regularizer': keras.regularizers.serialize(self.kernel_regularizer),
            'bias_regularizer': keras.regularizers.serialize(self.bias_regularizer),
            'kernel_constraint': keras.constraints.serialize(self.kernel_constraint),
            'bias_constraint': keras.constraints.serialize(self.bias_constraint),
            'attention_activation': keras.activations.serialize(self.attention_activation),
            'attention_regularizer_weight': self.attention_regularizer_weight,
        }
        base_config = super(SeqSelfAttention, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))

    def build(self, input_shape):
        if self.attention_type == SeqSelfAttention.ATTENTION_TYPE_ADD:
            self._build_additive_attention(input_shape)
        elif self.attention_type == SeqSelfAttention.ATTENTION_TYPE_MUL:
            self._build_multiplicative_attention(input_shape)
        super(SeqSelfAttention, self).build(input_shape)

    def _build_additive_attention(self, input_shape):
        feature_dim = int(input_shape[2])

        self.Wt = self.add_weight(shape=(feature_dim, self.units),
                                  name='{}_Add_Wt'.format(self.name),
                                  initializer=self.kernel_initializer,
                                  regularizer=self.kernel_regularizer,
                                  constraint=self.kernel_constraint)
        self.Wx = self.add_weight(shape=(feature_dim, self.units),
                                  name='{}_Add_Wx'.format(self.name),
                                  initializer=self.kernel_initializer,
                                  regularizer=self.kernel_regularizer,
                                  constraint=self.kernel_constraint)
        if self.use_additive_bias:
            self.bh = self.add_weight(shape=(self.units,),
                                      name='{}_Add_bh'.format(self.name),
                                      initializer=self.bias_initializer,
                                      regularizer=self.bias_regularizer,
                                      constraint=self.bias_constraint)

        self.Wa = self.add_weight(shape=(self.units, 1),
                                  name='{}_Add_Wa'.format(self.name),
                                  initializer=self.kernel_initializer,
                                  regularizer=self.kernel_regularizer,
                                  constraint=self.kernel_constraint)
        if self.use_attention_bias:
            self.ba = self.add_weight(shape=(1,),
                                      name='{}_Add_ba'.format(self.name),
                                      initializer=self.bias_initializer,
                                      regularizer=self.bias_regularizer,
                                      constraint=self.bias_constraint)

    def _build_multiplicative_attention(self, input_shape):
        feature_dim = int(input_shape[2])

        self.Wa = self.add_weight(shape=(feature_dim, feature_dim),
                                  name='{}_Mul_Wa'.format(self.name),
                                  initializer=self.kernel_initializer,
                                  regularizer=self.kernel_regularizer,
                                  constraint=self.kernel_constraint)
        if self.use_attention_bias:
            self.ba = self.add_weight(shape=(1,),
                                      name='{}_Mul_ba'.format(self.name),
                                      initializer=self.bias_initializer,
                                      regularizer=self.bias_regularizer,
                                      constraint=self.bias_constraint)

    def call(self, inputs, mask=None, **kwargs):
        # Use tf.shape instead of K.shape for compatibility
        input_shape = tf.shape(inputs)
        batch_size, input_len = input_shape[0], input_shape[1]

        if self.attention_type == SeqSelfAttention.ATTENTION_TYPE_ADD:
            e = self._call_additive_emission(inputs, batch_size, input_len)
        elif self.attention_type == SeqSelfAttention.ATTENTION_TYPE_MUL:
            e = self._call_multiplicative_emission(inputs, batch_size)

        if self.attention_activation is not None:
            e = self.attention_activation(e)
            
        if self.attention_width is not None:
            if self.history_only:
                lower = tf.range(0, input_len) - (self.attention_width - 1)
            else:
                lower = tf.range(0, input_len) - self.attention_width // 2
            lower = tf.expand_dims(lower, axis=-1)
            upper = lower + self.attention_width
            indices = tf.expand_dims(tf.range(0, input_len), axis=0)
            
            # Create attention mask
            attention_mask = tf.logical_and(
                tf.greater_equal(indices, lower),
                tf.less(indices, upper)
            )
            attention_mask = tf.cast(attention_mask, tf.float32)
            
            # Apply mask by adding large negative values to masked positions
            e -= 10000.0 * (1.0 - attention_mask)
            
        if mask is not None:
            # Expand mask for attention
            mask = tf.expand_dims(tf.cast(mask, tf.float32), axis=-1)
            mask_t = tf.transpose(mask, [0, 2, 1])
            
            # Apply input mask to e
            mask_matrix = tf.matmul(mask, mask_t)
            e -= 10000.0 * (1.0 - mask_matrix)

        # Apply softmax to get attention weights
        # First subtract max for numerical stability
        e_max = tf.reduce_max(e, axis=-1, keepdims=True)
        e_stable = e - e_max
        e_exp = tf.exp(e_stable)
        a = e_exp / tf.reduce_sum(e_exp, axis=-1, keepdims=True)

        # Apply attention weights to input
        v = tf.matmul(a, inputs)
        
        if self.attention_regularizer_weight > 0.0:
            self.add_loss(self._attention_regularizer(a, batch_size, input_len))

        if self.return_attention:
            return [v, a]
        return v

    def _call_additive_emission(self, inputs, batch_size, input_len):
        # h_{t, t'} = \tanh(x_t^T W_t + x_{t'}^T W_x + b_h)
        q = tf.expand_dims(tf.matmul(inputs, self.Wt), 2)  # (batch_size, input_len, 1, units)
        k = tf.expand_dims(tf.matmul(inputs, self.Wx), 1)  # (batch_size, 1, input_len, units)
        
        if self.use_additive_bias:
            h = tf.tanh(q + k + self.bh)
        else:
            h = tf.tanh(q + k)

        # e_{t, t'} = W_a h_{t, t'} + b_a
        # Reshape h to (batch_size * input_len * input_len, units)
        h_reshaped = tf.reshape(h, (-1, self.units))
        
        # Apply Wa
        attention = tf.matmul(h_reshaped, self.Wa)
        
        if self.use_attention_bias:
            attention += self.ba
            
        # Reshape back to (batch_size, input_len, input_len)
        e = tf.reshape(attention, (batch_size, input_len, input_len))
        return e

    def _call_multiplicative_emission(self, inputs, batch_size):
        # e_{t, t'} = x_t^T W_a x_{t'} + b_a
        projection = tf.matmul(inputs, self.Wa)  # (batch_size, input_len, feature_dim)
        
        # Perform batch dot product
        e = tf.matmul(projection, inputs, transpose_b=True)  # (batch_size, input_len, input_len)
        
        if self.use_attention_bias:
            e += self.ba[0]
        
        return e

    def compute_output_shape(self, input_shape):
        output_shape = input_shape
        if self.return_attention:
            attention_shape = (input_shape[0], output_shape[1], input_shape[1])
            return [output_shape, attention_shape]
        return output_shape

    def compute_mask(self, inputs, mask=None):
        if self.return_attention:
            return [mask, None]
        return mask

    def _attention_regularizer(self, attention, batch_size, input_len):
        # Create an identity matrix
        eye = tf.eye(input_len)
        
        # Calculate attention similarity: a·a^T
        attention_similarity = tf.matmul(attention, tf.transpose(attention, [0, 2, 1]))
        
        # Calculate squared difference from identity
        squared_diff = tf.square(attention_similarity - eye)
        
        # Sum all elements and normalize by batch size
        reg = self.attention_regularizer_weight * tf.reduce_sum(squared_diff) / tf.cast(batch_size, tf.float32)
        
        return reg

    @staticmethod
    def get_custom_objects():
        return {'SeqSelfAttention': SeqSelfAttention}