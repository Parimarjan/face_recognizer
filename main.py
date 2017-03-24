import numpy as np
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from matplotlib.cbook import get_sample_data
import cv2
import time
import os
import pickle
import hashlib
import random

from tsne import *
from sklearn.cluster import KMeans
from sklearn.cluster import AffinityPropagation
from sklearn.cluster import DBSCAN

from timeit import default_timer as now

# import copy
from PIL import Image
import math

import face_recognition
import dlib

# Note: If want to turn caffe output on/off then toggle GLOG_minloglevel
# environment variable.

# Arbitrarily chosen - because it seemed to be identifying people correctly
CLUSTERS = 4
PICKLE = True
TSNE_PICKLE = False
CENTER = True

# Use opencv to display images in same cluster (on local comp)
DISP_IMGS = False
SAVE_COMBINED = True

DATA_DIR = 'data'
# Change this appropriately
IMG_DIRECTORY = os.path.join(DATA_DIR, 'twilight1_imgs/')

# caffe files
# model = 'nets/VGG_FACE_deploy.prototxt';
# weights = 'nets/VGG_FACE.caffemodel';

def load_names():
    # Let's set up the names to check if we are right or wrong
    f = open('./data/names.txt')
    names = f.read()
    names = names.split('\n')
    f.close()
    return names

def load_img_files():

    file_names = os.listdir(IMG_DIRECTORY)
    imgs = []

    for i, name in enumerate(file_names):	

        # this was just a tmp folder I was using for processed images
        if 'proc' in name:
            continue
        imgs.append(IMG_DIRECTORY + name)  	

    return imgs

def get_features(imgs, names):
    '''
    Checks pickle for precomputed data, otherwise runs the caffe stuff on the
    all images in imgs.
    '''
    
    imgs.sort()
    
    # pickle it later 
    pickle_name = gen_pickle_name(imgs, 'face_recog')
    features = do_pickle(PICKLE, pickle_name, 1, run_face_recog, imgs)
       
    # features = run_face_recog(imgs) 
    sanity_check_features(features)

    return np.array(features)
    
def centralize(img):
    '''
    img is an np array - width, height, 3.
    centers and crops it - then returns img.

    Based on faceCrop.m from the vgg matconvnet code

    FIXME: should compare outputs with matlab script for correctness...
    '''
    # Because we already have a cropped face - will deal with it as if the
    # whole image is the bounding box

    extend = 0.1
    x1, y1 = 0, 0
    x2, y2, _ = img.shape
    width = round(x2-x1)
    height = round(y2-y1)

    length = (width + height) / 2
    centrepoint = [round(x1) + width/2, round(y1) + height/2]
    x1 = centrepoint[0] - round(1+extend)*(length/2)
    y1 = centrepoint[1] - round(1+extend)*(length/2)
    x2 = centrepoint[0] + round(1+extend)*(length/2)
    y2 = centrepoint[1] + round(1+extend)*(length/2)

    x1 = int(max(0, x1))
    y1 = int(max(0, y1))
    x2 = int(min(x2, img.shape[0]))
    y2 = int(min(y2, img.shape[1]))

    img = img[x1:x2, y1:y2,:]

    return img

def run_face_recog(img_files):
    '''
    Main loop in which we use caffe to recognize / score each of the images
    ''' 
    # imgs = []
    features = []
    
    bad_count = 0
    for i, img_file in enumerate(img_files):
        
        try:
            image = face_recognition.load_image_file(img_file)
        except IOError:
            print('bad input')
            continue
        
        # a tuple in (top, right, bottom, left) order as wanted
        # TODO: Check the width vs height.
        bounding_box = (image.shape[1], image.shape[0], 0, 0) 

        encodings = face_recognition.face_encodings(image, [bounding_box], 50)
         
        if len(encodings) == 1:
            features.append(encodings[0]) 
            pass
        else:
            print('len of encodings is :( ', len(encodings))
            bad_count += 1

    print('ratio of bad encodings is ', float(bad_count)/len(img_files))
    print('len of features is ', len(features))
    
    return features

#FIXME: Combine these two functions
def gen_pickle_name(imgs, feature_layer):
    """
    Use hash of file names + which layer data we're storing. 
    """
    hashed_input = hashlib.sha1(str(imgs)).hexdigest()
    
    name = hashed_input + '_' + feature_layer

    directory = "./pickle/"

    return directory + name + ".pickle"

def tsne_gen_pickle_name(features):
    """
    Use hash of file names + which layer data we're storing. 
    """
    hashed_input = hashlib.sha1(str(features)).hexdigest()
    
    name = hashed_input + '_' + 'tsne' 

    directory = "./pickle/"

    return directory + name + ".pickle"


def random_clustering(all_feature_vectors, func, *args, **kwargs):

    clusters = func(**kwargs).fit(all_feature_vectors)
    return clusters

def get_labels(kmeans, imgs):
    '''
    '''
    # Visualizing the labels_ - this is comman to all the clustering
    # algorithms..

    label_names = {}
    for i, label in enumerate(kmeans.labels_):

        # predicted_name = preds[i]
        file_name = imgs[i]
        label = str(label)
        if label not in label_names:
            label_names[label] = []

        label_names[label].append(file_name)
    
    return label_names

def kmeans_clustering(all_feature_vectors, clusters):
    '''
    runs kmeans with mostly default values on all_feature_vectors - and then
    prints out the names <--> labels combinations in the end.

    Ideally, can then manually check if the faces clustered in the same label
    belong to the same person or not.
    '''

    kmeans = KMeans(n_clusters=clusters, random_state=0).fit(all_feature_vectors) 
    return kmeans

    # Gives too many clusters:
    # kmeans = AffinityPropagation(damping=0.50).fit(all_feature_vectors) 
        
    # kmeans = DBSCAN().fit(all_feature_vectors) 
    

def process_clusters(label_names, name=''):

    for l in label_names:

        # Let's use opencv to display imgs one by one here in this cluster
        if DISP_IMGS:
            wait = raw_input("press anything to start this label")
            for label in label_names[l]:
                
                file_name = label
                # open the image with opencv
                img = cv2.imread(file_name)
                cv2.imshow('ImageWindow', img)
                c = cv2.waitKey()
                if c == 'q':
                    break

                # wait for a keypress to go to next image

        # Let's save these in a nice view
        if SAVE_COMBINED:
            n = math.sqrt(len(label_names[l]))
            print('n = ', n)
            n = int(math.floor(n))
            
            rows = []
            for i in range(n):
                # i is the current row that we are saving.
                row = []
                for j in range(i*n, i*n+n, 1):
                    
                    file_name = label_names[l][j]
                    # row.append(cv2.imread(file_name))
                    try:
                        img = Image.open(file_name)
                    except:
                        print('couldnt open img')
                        continue
                    row.append(img)
                
                rows.append(combine_imgs(row, 'horiz'))

            final_image = combine_imgs(rows, 'vertical')

            print("going to save the image!...")

            file_name = get_cluster_image_name(name, label_names[l], l)
            
            print('file name is ', file_name)
            final_image.save(file_name, quality=100)

def get_cluster_image_name(name, lst, label):

    hashed_input = hashlib.sha1(str(lst)).hexdigest()

    movie = IMG_DIRECTORY.split('/')[-2]

    name = 'results/' + name + '_' + movie + '_' + hashed_input[0:5] + '_' + label + '.jpg'

    return name

def combine_imgs(imgs, direction):
    '''
    '''
    # pick the image which is the smallest, and resize the others to match it (can be arbitrary image shape here)
    min_shape = sorted([(np.sum(i.size), i.size) for i in imgs])[0][1]
    if 'hor' in direction:
        min_shape = (30,30)

    # imgs = [i.resize(min_shape, refcheck=False) for i in imgs]

    if 'hor' in direction:

        imgs_comb = np.hstack( (np.asarray( i.resize(min_shape, Image.ANTIALIAS) ) for i in imgs ) )
        imgs_comb = Image.fromarray(imgs_comb)
    else:
        
        imgs_comb = np.vstack( (np.asarray( i.resize(min_shape, Image.ANTIALIAS) ) for i in imgs ) )
        imgs_comb = Image.fromarray(imgs_comb)

    return imgs_comb

def imgscatter(x, y, images, ax=None, zoom=1):
    if ax is None:
        ax = plt.gca()

    x, y = np.atleast_1d(x, y)
    artists = []
    for x0, y0, img_name in zip(x, y, images):

        try:
            img = plt.imread(img_name)
        except:
            print('could nt read img')
            continue

        im = OffsetImage(img, zoom=zoom)
        ab = AnnotationBbox(im, (x0, y0), xycoords='data', frameon=False)
        artists.append(ax.add_artist(ab))

    ax.update_datalim(np.column_stack([x, y]))
    ax.autoscale()
    return artists

def run_tsne(all_feature_vectors, imgs):
    '''
    '''
    # assert len(all_feature_vectors) == len(preds), 'features and preds \
            # should be same length'

    # Since we don't have correct labels - maybe we should just plot it without
    # labels - will just be the same color.

    pickle_name = tsne_gen_pickle_name(all_feature_vectors)
    
    Y = do_pickle(TSNE_PICKLE, pickle_name, 1, tsne, all_feature_vectors)
    x = []
    y = []
    img_names = []

    for i, coord in enumerate(Y):
        #if random.randint(0,30) == 20:
        assert len(coord) == 2, 'coord not 2?'
        x.append(coord[0])
        y.append(coord[1])
        file_name = imgs[i]
        img_names.append(file_name)

    fig, ax = plt.subplots()
    imgscatter(x, y, img_names, zoom=0.5, ax=ax)
    ax.scatter(x,y)
    
    print('going to show the plot now...')

    hashed_names = hashlib.sha1(str(img_names)).hexdigest()
    file_name = 'tsne_plt_' + hashed_names[0:5] + '.png'
    
    print('tsne name is ', file_name)
    plt.savefig(file_name, dpi=1200)
    
    #FIXME: Better way to visualize this? 

    # this won't work on the halfmoon cluster so run it on a local machine
    #size = 20
    # Plot.scatter(Y[:,0], Y[:,1], size);
    # Plot.show();
    return Y
    
def do_pickle(pickle_bool, pickle_name, num_args, func, *args):
    '''
    General function to handle pickling.
    @func: call this guy to get the result if pickle file not available.

    '''
    if not pickle_bool:
        rets = func(*args)   
    elif os.path.isfile(pickle_name):
        #pickle exists!
        with open(pickle_name, 'rb') as handle:
            rets = []
            for i in range(num_args):
                rets.append(pickle.load(handle))

            print("successfully loaded pickle file!")    
            print(len(rets))
            rets = tuple(rets)
            print(len(rets))
            handle.close()

    else:
        rets = func(*args)
        
        # dump it for future
        with open(pickle_name, 'w+') as handle:
            for i in range(len(rets)):
                pickle.dump(rets[i], handle, protocol=pickle.HIGHEST_PROTOCOL) 
        handle.close()

    return rets

def sanity_check_features(features):

    # for layer in features:
    for i, row in enumerate(features):
        f1 = np.linalg.norm(row)
        assert f1 != 0, ':((('

def main():

    names = load_names()
    imgs = load_img_files()
    
    feature_vectors = get_features(imgs, names)
    
    # for clusters in [2,4,8]:

        # feature_vectors = all_features[layer]

        # kmeans = random_clustering(feature_vectors, KMeans, n_clusters=clusters)
        # labels = get_labels(kmeans, preds, names, imgs)
        # process_clusters(labels, name=layer+'_'+ str(clusters))

        # # do tsne based clustering now.
        # Y = run_tsne(feature_vectors, preds, names, imgs)
        # kmeans = random_clustering(Y, KMeans, n_clusters=clusters)

        # tsne_labels = get_labels(kmeans, preds, names, imgs)
        # process_clusters(tsne_labels, name='tsne'+ '_' + layer +'_'+  str(clusters))

            # other methods?

    
    clusters = 8
    kmeans = random_clustering(feature_vectors, KMeans, n_clusters=clusters)
    print('kmeans clustering done....')
    labels = get_labels(kmeans, imgs)
    process_clusters(labels, name=str(clusters))
    print('done with clustering..!')

    Y = run_tsne(feature_vectors, imgs)
    # tsne_labels = get_labels(kmeans, preds, names, img)
    # process_clusters(tsne_labels, name='tsne'+ '_' + layer +'_'+  str(clusters))

    DBS = random_clustering(feature_vectors, DBSCAN, eps=0.3)
    labels = get_labels(DBS, imgs)
    process_clusters(labels, name='DBS' + '_'+ 'fc8')
     
    AP = random_clustering(feature_vectors, AffinityPropagation)
    labels = get_labels(AP, imgs)
    process_clusters(labels, name='AP' +'_'+ 'fc8')

if __name__ == '__main__':

    main()
