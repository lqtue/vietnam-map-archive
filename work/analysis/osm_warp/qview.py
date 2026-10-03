from viz import *
from fastq import *
def qimage(box, step=4, bins_=None):
    x0,y0,w,h=box
    gy,gx=np.mgrid[y0:y0+h:step,x0:x0+w:step]
    X=gx.ravel().astype(float);Y=gy.ravel().astype(float)
    best=np.zeros(len(X),np.float32)
    for k in (range(NK) if bins_ is None else bins_):
        r,c=to_rot(X,Y,k*180.0/NK)
        best=np.maximum(best,map_coordinates(qmap(k,0),[r,c],order=1,mode='constant',cval=0.0))
    return best.reshape(gy.shape)
if __name__=='__main__':
    box=[int(v) for v in sys.argv[1:5]]
    im=crop(box); q=qimage(box)
    fig,ax=plt.subplots(1,2,figsize=(18,9))
    ax[0].imshow(im,extent=(box[0],box[0]+box[2],box[1]+box[3],box[1]))
    ax[1].imshow(im,extent=(box[0],box[0]+box[2],box[1]+box[3],box[1]),alpha=.5)
    ax[1].imshow(np.ma.masked_less(q,0.05),extent=(box[0],box[0]+box[2],box[1]+box[3],box[1]),vmin=0,vmax=1,cmap='autumn')
    plt.savefig(SP/'qview.png',dpi=60)
