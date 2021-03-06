# -*- coding: utf-8 -*-
"""
Created on Thu Jan  3 22:14:29 2019

@author: basi9
"""
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
all_data_info_true300 = pd.read_csv("data/all_data_info_true300.csv")

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

##############################################
##########  Transfer Learning with ResNet50 ##
##############################################

### Only for feature extraction as we practically only changed the output classes

from keras.applications.resnet50 import ResNet50
from keras.models import Model
from keras.layers import Dense, GlobalAveragePooling2D
from keras import backend as K

n_classes= len(artist_list)
base_model = ResNet50(input_shape=(224,224,3), weights='imagenet',include_top=False)
#
base_model.summary()

x = GlobalAveragePooling2D()(base_model.output)
#put or not keras.layers.?

# let's add a fully-connected layer
#x = keras.layers.Dense(1024, activation='relu')(x)

# we add a logistic/classification layer for our classes
output = Dense(n_classes, activation='softmax')(x)

# this is the model we will train
model50 = Model(inputs=base_model.input, outputs=output)

model50.summary()

# first: train only the top layers (which were randomly initialized)
# i.e. freeze all convolutional ResNet50 layers
for layer in base_model.layers:
    layer.trainable = False
#in fact
model50.summary()    

# compile the model (should be done *after* setting layers to non-trainable)
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
learning_rate_reduction = ReduceLROnPlateau(monitor='val_acc',factor=0.1,\
                                            patience=3,verbose=1,min_lr=0.0001)


model50.compile(optimizer='adam', loss='categorical_crossentropy',\
                metrics=['accuracy', top_1_categorical_accuracy, top_3_categorical_accuracy, precision, recall, F1_score])

time_start = datetime.now()
model50.fit_generator(generator=train_generator,\
                    steps_per_epoch=STEP_SIZE_TRAIN,\
                    validation_data=valid_generator,\
                    validation_steps=STEP_SIZE_VALID,\
                    verbose=2, epochs=11, callbacks=[learning_rate_reduction])
time_end = datetime.now()
print('Tempo di esecuzione per fit_gen: {}'.format(time_end-time_start))
model50.save('data/ResNet50_TOPonly_11epochs.h5')

# accuracy plots
import pickle
import os
os.system("mkdir dictionaries")
with open('dictionaries/ResNet50_TOPonly_11epochsDict.pkl', 'wb') as file_pi:
    pickle.dump(model50.history.history, file_pi)

# list all data in history
print(model50.history.history.keys())
# summarize history for accuracy
plt.figure()
plt.plot(model50.history.history['acc'])
plt.plot(model50.history.history['val_acc'])
plt.title('model accuracy')
plt.ylabel('accuracy')
plt.xlabel('epoch')
plt.legend(['train', 'test'], loc='upper left')
plt.savefig('ResNet50_TOPonly_11epochs.png')

#### Making predictions on validation set, Confusion Matrix and metrics
# we have to make the batch size of valid_generator to 1 so that
# it can divide exactly the number of instances in the validation set
best_valid_generator = valid_datagen.flow_from_dataframe(df, 'data/valid', target_size=(224, 224),\
 x_col='new_filename', y_col='artist', has_ext=True, seed=1,batch_size=1, shuffle=False, class_mode=None)

###   Predictions of valid set   ###
# get predictions of valid set
best_valid_generator.reset()   # reset is crucial!
preds = model50.predict_generator(generator=best_valid_generator, steps=len(best_valid_generator), verbose=1)

# get indices (numbers) associated to classes (authors)
predicted_class_indices = np.argmax(preds, axis=1)

# create set of labels in a dictionary
labels = train_generator.class_indices
labels = dict((v,k) for k,v in labels.items())
predictions = [labels[k] for k in predicted_class_indices]

paint_list_valid = open('data/paint_list_valid.txt', 'r').read().split('\n')
###   Confusion matrix   ###
# in the following steps I want to create a dataframe with the predictions and actual authors of the validation set
df_val = df[df['new_filename'].isin(paint_list_valid)]   #.artist
# df_val has the true artist in 'artist' column

# I create a dataframe with jpg names and predictions (I can do this since shuffle=False in best_valid_generator)
df_jpg_with_predictions = pd.DataFrame({'new_filename': best_valid_generator.filenames,
                                        'artist_predicted': predictions})

# merge the two dataframes
df_val_with_predictions = pd.merge(df_val, df_jpg_with_predictions, how='inner', on='new_filename', sort=False)

# create arrays for confusion matrix
y_true = np.asarray(df_val_with_predictions['artist'])
y_pred = np.asarray(df_val_with_predictions['artist_predicted'])
from sklearn.metrics import confusion_matrix
cm = confusion_matrix(y_true, y_pred)

with open('dictionaries/ResNet50_TOPonly_11epochsDict.pkl', 'rb') as file_pi:
    hist = pickle.load(file_pi)

#Writing metrics results in a txt file
acc_train = hist['acc'][9]
print('Training accuracy of best model is: {}'.format(acc_train))
evalu = model50.evaluate_generator(generator=valid_generator, steps=len(valid_generator))
acc_valid = evalu[1]
print('Validation accuracy of best model is: {}'.format(acc_valid))
# true precision/recall/F1_score of the model
precis = np.mean(np.diag(cm) / np.sum(cm, axis = 1))
print('Precision of best model is: {}'.format(precis))
rec = np.mean(np.diag(cm) / np.sum(cm, axis = 0))
print('Recall of best model is: {}'.format(rec))
f1 = 2 * ((precis * rec) / (precis + rec))
print('F1 Score of best model is: {}'.format(f1))
# top3 training and validation accuracy
acc_top3_train = hist['top_3_categorical_accuracy'][9]
print('Top-3 training accuracy of best model is: {}'.format(acc_top3_train))
acc_top3_valid = evalu[2]
print('Top-3 validation accuracy of best model is: {}'.format(acc_top3_valid))


#Writing everything in a txt
file = open("ResNet50_TOP_11epochs_metrics.txt", "w") 
file.write('Training accuracy of best model is: {}'.format(acc_train)) 
file.write('\nValidation accuracy of best model is: {}'.format(acc_valid)) 
file.write('\nPrecision of best model is: {}'.format(precis)) 
file.write('\nRecall of best model is: {}'.format(rec))
file.write('\nF1 Score of best model is: {}'.format(f1))
file.write('\nTop-3 training accuracy of best model is: {}'.format(acc_top3_train))
file.write('\nTop-3 validation accuracy of best model is: {}'.format(acc_top3_valid))
file.close() 

#Plot Confusion Matrix
plt.matshow(cm)
plt.title('Confusion matrix')
plt.colorbar()
plt.ylabel('True label')
plt.xlabel('Predicted label')
plt.savefig('ResNet50_TOP_11epochs_ConfusionMatrix.png')

