import numpy as np
import pandas as pd
import matplotlib.pylab as plt
import matplotlib.image as mpimg
import random
import sys
from datetime import datetime
# due righe sotto per caricare qualsiasi risoluzione di immagine
from PIL import Image
Image.MAX_IMAGE_PIXELS = None


# creo il dataset contenente i nomi dei file .jpg da leggere e le rispettive labels
all_data_info_true300 = pd.read_csv("all_data_info_true300.csv")

all_data_info_true300_count = all_data_info_true300.groupby('artist').count()
print(all_data_info_true300_count.shape)
artist_list = all_data_info_true300_count.index.values.tolist()

## Image processing to get the starting data for training the model
from keras.preprocessing.image import ImageDataGenerator

df = all_data_info_true300.loc[:, ['artist','new_filename']]

train_datagen = ImageDataGenerator(horizontal_flip=True)
valid_datagen = ImageDataGenerator(horizontal_flip=False)
#featurewise_center=True   0-center
#featurewise_std_normalization    normalize

train_generator = train_datagen.flow_from_dataframe(df,\
"data/train", \
target_size=(224, 224), x_col='new_filename',\
y_col='artist', has_ext=True, seed=100)
#Found 13680 images belonging to 57 classes.

valid_generator = valid_datagen.flow_from_dataframe(df,\
"data/valid",\
target_size=(224, 224), x_col='new_filename',\
y_col='artist', has_ext=True, seed=100)
#Found 1710 images belonging to 57 classes.

#color_mode='rgb' default
#has_ext has been deprecated, extensions included
#class_mode= default categorical
#batch_size: size of the batches of data (default: 32)

STEP_SIZE_TRAIN=train_generator.n//train_generator.batch_size
#i.e. 13680//32 = 427
STEP_SIZE_VALID=valid_generator.n//valid_generator.batch_size


###   ResNet18 - transfer learning   ###

# transfer learning
#making it doable on GPU
import tensorflow as tf
import keras 
from keras import backend as K 
config = tf.ConfigProto( device_count = {'GPU': 1 , 'CPU': 4} ) 
sess = tf.Session(config=config) 
keras.backend.set_session(sess)

# build model
from classification_models import ResNet18
n_classes = len(artist_list)
base_model = ResNet18(input_shape=(224,224,3), weights='imagenet', include_top=False)
x = keras.layers.GlobalAveragePooling2D()(base_model.output)
#not sure about adding flatten
x = keras.layers.Flatten(x)
x = keras.layers.Dropout(0.3)(x)
output = keras.layers.Dense(n_classes, activation='softmax')(x)
model_dropTOP18 = keras.models.Model(inputs=[base_model.input], outputs=[output])
model_dropTOP18.summary()

# We only train top layers, therefore we freeze the ResNet ones
len(model_dropTOP18.layers)
model_dropTOP18.layers[(len(model_dropTOP18.layers) - 2) : len(model.layers)]
for i in range(len(model_dropTOP18.layers) - 2):
    model_dropTOP18.layers[i].trainable = False
model_dropTOP18.summary()

from keras.metrics import top_k_categorical_accuracy

def top_1_categorical_accuracy(y_true, y_pred):
    return top_k_categorical_accuracy(y_true, y_pred, k=1)
def top_3_categorical_accuracy(y_true, y_pred):
    return top_k_categorical_accuracy(y_true, y_pred, k=3)
def precision(y_true, y_pred):
    """
    Precision metric.
    Only computes a batch-wise average of precision.
    Computes the precision, a metric for multi-label classification of how many selected items are relevant.
    """
    true_positives = K.sum(K.round(K.clip(y_true * y_pred, 0, 1)))
    predicted_positives = K.sum(K.round(K.clip(y_pred, 0, 1)))
    precis = true_positives / (predicted_positives + K.epsilon())
    return precis
def recall(y_true, y_pred):
    """
    Recall metric.
    Only computes a batch-wise average of recall.
    Computes the recall, a metric for multi-label classification of how many relevant items are selected.
    """
    true_positives = K.sum(K.round(K.clip(y_true * y_pred, 0, 1)))
    possible_positives = K.sum(K.round(K.clip(y_true, 0, 1)))
    rec = true_positives / (possible_positives + K.epsilon())
    return rec
def F1_score(y_true, y_pred):
    '''
    defined as the harmonic average of precision and recall,
    i.e.   2*p*r / (p+r)
    '''
    def precision(y_true, y_pred):
        """
        Precision metric.
        Only computes a batch-wise average of precision.
        Computes the precision, a metric for multi-label classification of how many selected items are relevant.
        """
        true_positives = K.sum(K.round(K.clip(y_true * y_pred, 0, 1)))
        predicted_positives = K.sum(K.round(K.clip(y_pred, 0, 1)))
        precis = true_positives / (predicted_positives + K.epsilon())
        return precis
    def recall(y_true, y_pred):
        """
        Recall metric.
        Only computes a batch-wise average of recall.
        Computes the recall, a metric for multi-label classification of how many relevant items are selected.
        """
        true_positives = K.sum(K.round(K.clip(y_true * y_pred, 0, 1)))
        possible_positives = K.sum(K.round(K.clip(y_true, 0, 1)))
        rec = true_positives / (possible_positives + K.epsilon())
        return rec
    precision = precision(y_true, y_pred)
    recall = recall(y_true, y_pred)
    return 2 * ((precision * recall) / (precision + recall + K.epsilon()))

from keras.callbacks import ReduceLROnPlateau
learning_rate_reduction = ReduceLROnPlateau(monitor='val_acc',\
                                            factor=0.1,\
                                            patience=3,\
                                            verbose=1,\
                                            min_lr=0.0001)
    
# training
model_dropTOP18.compile(optimizer='Adam', loss='categorical_crossentropy',\
              metrics=['accuracy', top_1_categorical_accuracy, top_3_categorical_accuracy, precision, recall, F1_score])
model_dropTOP18.fit_generator(generator=train_generator,\
                    steps_per_epoch=STEP_SIZE_TRAIN,\
                    validation_data=valid_generator,\
                    validation_steps=STEP_SIZE_VALID,\
                    epochs=30, verbose=2,callbacks=[learning_rate_reduction])
model_dropTOP18.save('data/ResNet18_dropTOP_30epochs.h5')  # TL sta per 'Transfer Learning'

# list all data in history
print(model_dropTOP18.history.history.keys())
# summarize history for accuracy
plt.plot(model_dropTOP18.history.history['acc'])
plt.plot(model_dropTOP18.history.history['val_acc'])
plt.title('model accuracy')
plt.ylabel('accuracy')
plt.xlabel('epoch')
plt.legend(['train', 'test'], loc='upper left')
plt.savefig('ResNet18_dropTOP_30epochs.png')

