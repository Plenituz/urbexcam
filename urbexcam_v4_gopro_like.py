import picamera
import io
import os
import time
import re
import RPi.GPIO as GPIO
import pyaudio
import wave
import subprocess
import _thread as thread

#audio parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 8192 #magic number don't change it 
#other parameters
PIN_BUTTON = 18
FOLDER = '/home/pi/Videos/'

#global vars
camera = None
path = None
pathNumber = -1
audio = None
streamAudio = None
hasAudio = True
recordAudio = True
audioHasStopped = False
stop = False


def stopEverything():
    global recordAudio
    global camera
    global streamAudio
    global audio
    global audioHasStopped
    
    print('stopping')
    
    recordAudio = False
    try:
        camera.stop_recording()
    except:
        pass
    try:
        GPIO.cleanup()
    except:
        pass
    if hasAudio:
        while audioHasStopped is False:
            pass #wait for audio thread to stop
        streamAudio.stop_stream()
        streamAudio.close()
        audio.terminate()
    #shutdown
    #subprocess.call("halt")

def exportAudioFile(buffer, pathToExport):  
    print('exporting audio to ' + pathToExport)
    waveFile = wave.open(pathToExport, 'wb')
    waveFile.setnchannels(CHANNELS)
    waveFile.setsampwidth(audio.get_sample_size(FORMAT))
    waveFile.setframerate(RATE)
    waveFile.writeframes(b''.join(buffer))
    waveFile.close()

def getNextPath():
    #returns the full path to the folder where to put the
    #before and after files
    content = os.listdir(FOLDER)
    greatest = 0
    
    for file in content:
        if os.path.isdir(FOLDER + file):
            regex = re.compile('plenicam_f_\d+').match(file)
            if(regex is not None):
                #file name is good, count it
                nb = int(file[11:])
                if(nb > greatest):
                    greatest = nb
    return ('{0}plenicam_f_{1}/'.format(FOLDER, greatest+1), greatest+1)

def nextAudioPath():
    #this assumes path is already filled and mkdir has been called
    #ie callable only after setup()
    global path

    content = os.listdir(path)
    greatest = 0

    for file in content:
        if 'audio_' in file:
            num = int(file[6:-4])
            if num > greatest:
                greatest = num
    return '{0}audio_{1}.wav'.format(path, greatest+1)

def setup():
    global camera
    global path
    global pathNumber 
    global audio
    global hasAudio
    global streamAudio

    #get path to store the video and create the folder
    path, pathNumber = getNextPath()
    os.mkdir(path)
    print('path={0}, number={1}'.format(path, pathNumber))

    #cleanup GPIO, you never know where it's been
    #kinda like yo mama
    GPIO.cleanup()
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN_BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(PIN_BUTTON, GPIO.FALLING,
                          button_down_callback, 1000)

    camera = picamera.PiCamera()
    camera.framerate = 25 #might have to change the framerate to sync better with audio
    #camera.resolution = (1920,1080) #this resolution is a bit zoomed in but youtube friendly
    camera.resolution = (1296, 972) #this resolution if full sensor on the standard picamv2


    try:
        audio = pyaudio.PyAudio()
        streamAudio = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                                 input=True, frames_per_buffer=CHUNK)
    except OSError:
        #if there is no microphone plugged in, OSError is thrown
        hasAudio = False
    print('hasAudio=%s' % hasAudio)

    #start recording audio in it's own thread
    if hasAudio:
        thread.start_new_thread(audio_recording_thread, ())
    #start recording video in the given folder
    camera.start_recording('{0}plenicam_vid_{1}.h264'.format(path, pathNumber))

def audio_recording_thread():
    global hasAudio
    if hasAudio is False:
        return

    global streamAudio
    global recordAudio
    global audioHasStopped

    frames = []
    while recordAudio:
        try:
            data = streamAudio.read(CHUNK)
            if recordAudio is False:
                break
            frames.append(data)
        except OSError:
            print("skipped audio frame")
        if recordAudio is False:
                break
        #every 100 audio frames, export it to a file so
        #the ram is not filled and you don't loose
        #everything if it crashes
        if len(frames) > 100:
            exportAudioFile(frames, nextAudioPath())
            frames = []
    #recording is done
    exportAudioFile(frames, nextAudioPath())
    audioHasStopped = True

def button_down_callback(arg):
    if(GPIO.input(PIN_BUTTON) == 1):
        print('false input down')
        return
    global stop
    stop = True

    print('press')
    

setup()
try:
    while stop is False:
        pass
except KeyboardInterrupt:
    pass
stopEverything()
