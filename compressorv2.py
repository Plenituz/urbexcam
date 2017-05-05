import subprocess
import io
from natsort import natsorted
import os
from pathlib import Path

#the dir has to end with \\
dir = 'D:\\_CODING\\github_clone\\urbexcam\\out\\'
def compressh264toMp4InFolder(fullPath):
    print('compressing all .h264 in {0}'.format(fullPath))
    folderContent = os.listdir(fullPath)
    for fileName in folderContent:
        if(fileName[-5:] == '.h264'):
            print('found {0} in {1}'.format(fileName, fullPath))
            compressh264ToMp4(fullPath + '\\' + fileName)
    print('done compressing in {0}'.format(fullPath))

def compressh264ToMp4(h264FileFullPath):
    outFile = h264FileFullPath.replace('h264', 'mp4')
    print("compressing {0} into {1}".format(h264FileFullPath, outFile))
    result = subprocess.call(['ffmpeg', '-i', h264FileFullPath, '-c:v', 'h264', outFile])
    if result == 0:
        print("compressing done, deleting .h264 file")
        os.remove(h264FileFullPath)
    else:
        print('compressing failed, moving on')

def stitchAudioFilesInFolder(fullPath):
    print('stitching audio files in {0}'.format(fullPath))
    folderContent = os.listdir(fullPath)
    filesToStitch = []
    textFilePath = fullPath + '\\' + 'stitch.txt'
    outFile = fullPath + '\\' + 'plenicam_vid_audio.wav'

    for fileName in folderContent:
        if fileName[-4:] == '.wav':
            filesToStitch.append((fullPath + '\\' + fileName).replace('\\', '/'))

    filesToStitch = natsorted(filesToStitch)
    if len(filesToStitch) <= 1:
        print('not enough files to stitch, must have already been here, moving on')
        return

    
    textFile = open(textFilePath, "w")
    for file in filesToStitch:
        textFile.write("file {0}\n".format(file))
    textFile.close()

    result = subprocess.call(['ffmpeg', '-f', 'concat', '-safe', '0', '-i', textFilePath,
                     '-c', 'copy', outFile])
    if result == 0:
        print('stitch sucessful, deleting stiched .wav files')
        for file in filesToStitch:
            os.remove(file)
    else:
        print('stiching error, moving on')
    os.remove(textFilePath)
    
    
#todo extract video from folder if there is no
print('salut')
masterContent = os.listdir(dir)
for masterFile in masterContent:
    print(masterFile)
    if os.path.isdir(dir + masterFile):
        compressh264toMp4InFolder(dir + masterFile)
        stitchAudioFilesInFolder(dir + masterFile)
