# -*- coding: utf-8 -*-
"""
Created on Thu Jun 10 06:19:35 2021

@author: Hoang Van Do
"""

import PySpin
import numpy as np
from PIL import Image
import scipy.optimize as opt
import wx


"Setting parameters"
#cropzone=[1,1024-1,1,1280-1]
cropzone=[400,1024-530, 520,1280-630] 
cropsize=20
if cropsize>0.5*(cropzone[1]-cropzone[0]) or cropsize>0.5*(cropzone[3]-cropzone[2]):
    raise ValueError("Crop size is too wilde")
camindex=0
set_exp_time=270000. #us
set_gain=2. #dB
StreamWindowSize = (cropzone[1]-cropzone[0]+20, cropzone[3]-cropzone[2]+20)

"initialize PySpin instance"
PySpin.System.GetInstance()



"Start camera"
def MOTCam(serialorindex=camindex):
    if isinstance(serialorindex,int):
        MOTCamera=PySpin.System.GetInstance().GetCameras().GetByIndex(serialorindex)
    elif isinstance(serialorindex, str):
        MOTCamera=PySpin.System.GetInstance().GetCameras().GetBySerial(serialorindex)
    MOTCamera.Init()
    return MOTCamera
MOTCam().BeginAcquisition()

def GaussianFunc(x,y,amp,mux,muy,sigx,sigy):
    return amp*np.exp(-(((x - mux)/(np.sqrt(2)*sigx))**2 + ((y - muy)/(np.sqrt(2)*sigy))**2))

"Get MOT image and number of atoms"
class MOTLive:        
    def __init__(self,MOTCamera):
        self.MOTCamera=MOTCamera
        self.MOTCamera.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
        self.MOTCamera.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
        self.MOTCamera.ExposureTime.SetValue(set_exp_time)
        self.MOTCamera.GainAuto.SetValue(PySpin.GainAuto_Off)
        self.MOTCamera.Gain.SetValue(set_gain)
        #self.MOTCamera.BeginAcquisition()      
    def MOTimage(self):
        return Image.fromarray(self.MOTCamera.GetNextImage().GetNDArray()[cropzone[0]:cropzone[1],cropzone[2]:cropzone[3]])
    def NAtoms(self):
        img=self.MOTCamera.GetNextImage().GetNDArray()[cropzone[0]:cropzone[1],cropzone[2]:cropzone[3]]
        if np.amax(img)<75 or np.amax(img)>500:
            return 0
        else:
            maxpos=np.unravel_index(img.argmax(), img.shape)
            img=img[maxpos[0]-round(cropsize/2):maxpos[0]+round(cropsize/2),maxpos[1]-round(cropsize/2):maxpos[1]+round(cropsize/2)]
            x, y = np.array(range(cropsize)), np.array(range(cropsize))
            X, Y = np.meshgrid(x, y)
            axisdata = np.vstack((X.ravel(), Y.ravel()))        
            guess_prms=[np.amax(img), cropsize/2, cropsize/2, 3, 3]   
            def _gaussian(M, *args):
                x, y = M
                arr = np.zeros(x.shape)
                for i in range(len(args)//5):
                   arr += GaussianFunc(x, y, *args[i*5:i*5+5])+np.amin(img)
                return arr
            popt, pcov = opt.curve_fit(_gaussian, axisdata, img.ravel(), guess_prms)
            fit = np.zeros(img.shape)
            for i in range(len(popt)//5):
                fit += GaussianFunc(X, Y, *popt[i*5:i*5+5])+np.amin(img)
            return(np.absolute(2*np.pi*popt[0]*np.prod(popt[3:4])))
        
def pil_to_wx(image):
    width, height = np.shape(image)
    buffer = image.convert('RGB').tobytes()
    bitmap = wx.Bitmap.FromBuffer(width, height, buffer)
    return bitmap

class Panel(wx.Panel):
    def __init__(self, parent):
        super(Panel, self).__init__(parent, -1)
        self.SetSize(StreamWindowSize)
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.update()
    def update(self):
        self.Refresh()
        self.Update()
        wx.CallLater(15, self.update)
    def create_bitmap(self):
        image = MOTLive(MOTCam()).MOTimage()
        bitmap = pil_to_wx(image)
        return bitmap
    def on_paint(self, event):
        bitmap = self.create_bitmap()
        dc = wx.AutoBufferedPaintDC(self)
        dc.DrawBitmap(bitmap, 0, 0)

LastNAtoms=MOTLive(MOTCam()).NAtoms()

class Frame(wx.Frame):
    def __init__(self):
        style = wx.DEFAULT_FRAME_STYLE & ~wx.RESIZE_BORDER & ~wx.MAXIMIZE_BOX
        super(Frame, self).__init__(None, -1, 'Camera Viewer', style=style)
        panel = Panel(self)
        self.Fit()

def main():
    app = wx.App()
    frame = Frame()
    frame.Center()
    frame.Show()
    app.MainLoop()

if __name__ == '__main__':
    main()

MOTCam().EndAcquisition()
PySpin.System.ReleaseInstance()
