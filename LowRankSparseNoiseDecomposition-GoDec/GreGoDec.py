#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===========================================================================
                Greedy Semi-Soft GoDec Algotithm (GreBsmo)
===========================================================================

===========================================================================
Instructions : 
    DecomposeGoDec("Samples/Escalator.avi", length = int)
    The code works with grayscale tif stacks or RGB avi files
    if length = 0 ,all the frames are loaded
===========================================================================

===========================================================================
REFERENCE:
 Tianyi Zhou and Dacheng Tao, "GoDec: Randomized Lo-rank & Sparse Matrix
 Decomposition in Noisy Case", ICML 2011
 Tianyi Zhou and Dacheng Tao, "Greedy Bilateral Sketch, Completion and 
 Smoothing", AISTATS 2013.
 Tianyi Zhou, 2013, All rights reserved.
===========================================================================

===========================================================================
Python Implementation : J. Fattaccioli (Department of Chemisrty, ENS)
Date : March 2020
Requirements : 
Python==3.7.5
scipy==1.3.1
scikit_image==0.15.0
numpy==1.17.3
PyWavelets==1.0.3
skimage==0.0
===========================================================================

"""
    
import skimage.external.tifffile as tif
import numpy as np
import scipy as sc
import cv2 as cv
import pywt

def DecomposeGoDec(NameFile, rank = 3, power = 5, tau= 7, tol= 0.001, k = 2, dynamicrange = 8, length = 0):
    """
    default rank =3
    default power = 5
    default tau = 7
    default tol = 0.001
    default k = 1
    default lenght = 0
    """
    StartingImage, NImage, HImage, WImage= import_image(NameFile, length)
    print("Image Loading OK")
    FinalImage=np.zeros((NImage, HImage*WImage), dtype=int)
    FinalImage=vectorize(StartingImage,NImage, HImage, WImage )
    print("Image Vectorization OK")

    D, L, S = GreGoDec(FinalImage, rank, tau, tol, power, k)
    G = D-L-S
    print("GoDec OK")

    D = reconstruct(D, HImage, WImage, NImage, "1-Original.tif", dynamicrange)
    L = reconstruct(L, HImage, WImage, NImage, "2-Background.tif", dynamicrange)
    print("Reconstruction Low-rank OK")

    S = reconstruct(S, HImage, WImage, NImage, "3-Sparse.tif", dynamicrange)
    print("Reconstruction Sparse OK")

    G = reconstruct(G, HImage, WImage, NImage, "4-Noise.tif", dynamicrange)
    print("Full Process OK")
    return 




def import_image(NameFile,length):
    """
    String*float -> np.array(N,H,W)
    Retrieve an tiff image stack in a numpy array
    lenght : maximum number of frames. By default, length=0 and all frames are loaded
    """
    
    NameFileParsed = NameFile.split(".")
    
    if NameFileParsed[1]== ("tif" or "tiff"): 
        Image=tif.imread(NameFile)
        Image.astype(float)
        if length > Image.shape[0]:
           raise Exception("The length should be smaller than the number of frames") 
           
        if length!=0:
            Image=Image[:length,]
        print("TIF stack loading OK")
        
    elif NameFileParsed[1] == "avi":
        Cap = cv.VideoCapture(NameFile)
        Length = int(cv.VideoCapture.get(Cap, int(cv.CAP_PROP_FRAME_COUNT)))
        print(Length)
        print(length)
        if length > Length:
           raise Exception("The length should be smaller than the number of frames") 
           
        if length!=0:
            Length=length
            
        Width  = int(cv.VideoCapture.get(Cap, int(cv.CAP_PROP_FRAME_WIDTH)))
        Height = int(cv.VideoCapture.get(Cap, int(cv.CAP_PROP_FRAME_HEIGHT)))
        Temp = np.zeros((Length, Height, Width))
        
        for framenumber in range(Length):
            if (framenumber+1)%10==0:
                print("Frame number = ", framenumber+1)
                
            ret, frame = Cap.read()
            # if frame is read correctly ret is True
            if not ret:
                print("Can't receive frame (stream end?). Exiting ...")
                break
            Temp[framenumber::] = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)

        Cap.release()
        Image = Temp
        print("AVI loading OK")
    else :
        raise Exception("The file extension should be .tif, .tiff or .avi.")
    
    NImage=Image.shape[0]
    HImage=Image.shape[1]
    WImage=Image.shape[2]
    return Image, NImage, HImage, WImage

def vectorize(Image, NImage, HImage, WImage):
    """
    nparray(N, H, W)*int*int*int -> np.array(N,H*W)
    Convert the image stack (3d) in 2D
    This function is necessary to perform the GoDec process
    """
    
    FinalImage=np.zeros((NImage, HImage*WImage))
    for i in range(NImage):
        FinalImage[i,:]=np.reshape(Image[i, :, :], HImage*WImage)
    
    return FinalImage

def reconstruct(vector, line, col, time, name, dynamicrange):
    """
    np.array(N,H*W)*H(int)*W(int)*N(int)*str*int -> nparray(N, H, W)
    Reconstruct the image stacks after the GoDecprocess
    Save the nparray in a tif stack 'path' with the given dynamic range ( 8 or 16)
    """
    image=np.zeros((time, line, col))
    for i in range(time-1):
        temp=vector[i,:]
        image[i,:,:]=temp.reshape((line, col))
    save(image, name, dynamicrange) 
    
    return 

def save(data, path, dynamicrange):
    """
    nparray*str*int -> *
    This function save the nparray data as tif file with a given dynamic range
    Dynamic range = 8 or 16
    """
    
    #Conversion of the pixel values in uint8
    data=((data-np.amin(data))/np.amax(data-np.amin(data)))*(2**dynamicrange-1)
    if dynamicrange == 8:
        data=data.astype(np.uint8)
    elif dynamicrange == 16:
         data=data.astype(np.uint16)
    else:
        raise Exception("The dynamic range should be equal to 8 or 16 (bits)")
       
    #Saving tif file
    tif.imsave(path, data) 
    
    return
   
def GreGoDec(D,rank,tau,tol,power,k):
    """ 
    INPUTS:
    D: nxp data matrix with n samples and p features
    rank: rank(L)<=rank
    tau: soft thresholding
    power: >=0, power scheme modification, increasing it lead to better 
    accuracy and more time cost
    k: rank stepsize
    
    OUTPUTS:
    D : Input data matrix
    L:Low-rank part
    S:Sparse part
    
    The code uses these functions : 
    https://pywavelets.readthedocs.io/en/latest/ref/thresholding-functions.html
    https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.linalg.svds.html
    """            
    #Transposition in case the array has a wrong shape
   
    if D.shape[0] < D.shape[1]:
        D=np.transpose(D)
    
    normD=np.linalg.norm(D)
    #initialization of L and S
    rankk=round(rank/k)
    error=np.zeros((rank*power, 1), dtype=float)
    
    #Computation of the singular values
    X,s,Y = sc.sparse.linalg.svds(D, k)

    
    s=s*np.identity(k)
    X=X.dot(s)
    L=X.dot(Y)
    
    #Wavelet thresholding functions
    #https://pywavelets.readthedocs.io/en/latest/ref/thresholding-functions.html
    S=pywt.threshold(D-L, tau, 'soft')
    
    #Calcul de l'erreur
    T=D-L-S
    error[0]=np.linalg.norm(T)/normD

    iii=1
    stop=False
    alf=0
    for r in range(1,rankk+1):
        r=r-1
        #parameters for alf
        rrank=rank
        est_rank = 1 #Est_rank est toujours = à 1 (?) ?
        alf=0
        increment=1
        
        if iii==power*(r-2)+1:
            iii=iii+power
        for iter in range(1,power+1):
            
            #Update of X
            X=abs(L.dot(np.transpose(Y)))
            
            #Décomposition QR de la matrice X=L*Y'
            X, R =np.linalg.qr(X)
            
            #Update of Y
            Y=np.transpose(X).dot(L)
            L=X.dot(Y)
            #Update of S
            T=D-L
            S=pywt.threshold(T, tau, mode='soft')

            
            #Error, stopping criteria
            T=T-S
            ii=iii+iter-1
            
            error[ii]=np.linalg.norm(T)/np.linalg.norm(D)
            
            if error[ii]<tol:
                stop=True
                break
            
            if rrank != rank:
                rank = rrank
                if est_rank == 0:
                    alf = 0
                    continue
            
            #Adjust alf
            ratio=error[ii]/error[ii-1]
            #Interzmediate variables
            X1 = X
            Y1 = Y
            L1 = L
            S1 = S
            T1 = T

            if ratio >= 1.1:
                increment = max(0.1*alf, 0.1*increment)
                X=X1
                Y=Y1
                L=L1
                S=S1
                T=T1
                error[ii]=error[ii-1]
                alf=0
                
            elif ratio > 0.7:
                increment=max(increment, 0.25*alf)
                alf = alf + increment
            
            #Update of L
            X1 = X
            Y1 = Y
            L1 = L
            S1 = S
            T1 = T
            L = L + (1+alf)*T
            
            #Add corest
            if iter >8: 
                if np.mean(np.divide(error[ii-7:ii],error[ii-8]))>0.92:
                    iii=ii
                    
                    if Y.shape[1]-X.shape[0]>=k:
                        Y=Y[0:X.shape[0]-1, :]   
                    break
    
        #Stop
        if stop==True:
            break
        
        #Coreset
        if r+1<rankk:
            RR=np.random.randn(k, D.shape[0])
            v=RR.dot(L)
            Y=np.block([[Y], [v]])

   
    #error[error==0]=[]
    error=[error!=0]
    L=X.dot(Y)
    
    if D.shape[0]>D.shape[1]:
        L=np.transpose(L)
        S=np.transpose(S)
                           
    return np.transpose(D), L, S

