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
CHUNK = 8192

PRE_RECORD_TIME = 10
PIN_BUTTON = 18
PIN_LED = 23
PIN_BUZZER = 21
FOLDER = '/home/pi/Videos/'

looping = True
continueProg = True
camera = None
streamVideo = None
path = None
audio = None
streamAudio = None
recordAudio = True
button_being_pressed = False
shutdown = False
maxAudioBuffer = int(RATE / CHUNK * PRE_RECORD_TIME)

#fonctionnalities
hasAudio = True

def shutdownSound():
    GPIO.output(PIN_BUZZER, 1)
    time.sleep(3)
    GPIO.output(PIN_BUZZER, 0)

def startupSound():
    GPIO.output(PIN_BUZZER, 1)
    time.sleep(0.1)
    GPIO.output(PIN_BUZZER, 0)
    time.sleep(0.1)
    GPIO.output(PIN_BUZZER, 1)
    time.sleep(0.1)
    GPIO.output(PIN_BUZZER, 0)
    time.sleep(0.1)
    GPIO.output(PIN_BUZZER, 1)
    time.sleep(0.5)
    GPIO.output(PIN_BUZZER, 0)

def recordingSound():
    delay = 0.1
    for n in range(0, 4):
        GPIO.output(PIN_BUZZER, 1)
        time.sleep(delay)
        GPIO.output(PIN_BUZZER, 0)
        time.sleep(delay)

def endSound():
    GPIO.output(PIN_BUZZER, 1)
    time.sleep(1)
    GPIO.output(PIN_BUZZER, 0)

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
    return '{0}plenicam_f_{1}/'.format(FOLDER, greatest+1)

def nextAudioPath():
    #this assumes path is already filled and mkdir has been called
    global path

    content = os.listdir(path)
    greatest = 0

    for file in content:
        if 'audio_' in file:
            num = int(file[6:-4])
            if num > greatest:
                greatest = num
    return '{0}audio_{1}.wav'.format(path, greatest+1)

def LED_recording_thread():
    time.sleep(5)
    sta = True
    while continueProg:
        GPIO.output(PIN_LED, sta)
        sta = not sta
        time.sleep(.5)

def setup():
    global camera
    global streamVideo
    global path
    global audio
    global hasAudio
    global streamAudio

    path = getNextPath()
    os.mkdir(path)
    
    GPIO.cleanup()
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN_BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(PIN_LED, GPIO.OUT, initial=0)
    GPIO.setup(PIN_BUZZER, GPIO.OUT, initial=0)
    GPIO.add_event_detect(PIN_BUTTON, GPIO.FALLING,
                          button_down_callback, 5000)

    camera = picamera.PiCamera()
    #camera.framerate = 24
    #camera.resolution = (1920,1080)
    camera.resolution = (1296, 972)
    streamVideo = picamera.PiCameraCircularIO(camera,
                                              seconds=PRE_RECORD_TIME)

    try:
        audio = pyaudio.PyAudio()
        streamAudio = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                                 input=True, frames_per_buffer=CHUNK)
    except OSError:
        hasAudio = False
    print('hasAudio=%s' % hasAudio)
    
    camera.start_recording(streamVideo, format='h264')
    thread.start_new_thread(loopRecordAudio, ())
    thread.start_new_thread(startupSound, ())

def loopRecordAudio():
    global looping
    global hasAudio
    global maxAudioBuffer
    global CHUNK
    global streamAudio

    frames = []
    buffer = []
    
    if hasAudio is False:
        return
    while looping:
        for i in range(0, maxAudioBuffer):
            if looping is False:
                break
            try:
                data = streamAudio.read(CHUNK)
                frames.append(data)
            except OSError:
                print('skipped audio frame (loop)')
        if looping is False:
            break
        buffer = frames
        frames = []
    if len(buffer) == 0:
        toWrite = frames
    else:
        toWrite = buffer[-(maxAudioBuffer - len(frames)):] + frames
    exportAudioFile(toWrite, nextAudioPath())
    

def recordAudio():
    global hasAudio
    if hasAudio is False:
        return
    
    global streamAudio
    global maxAudioBuffer
    global CHUNK
    global recordAudio

    frames = []
    while recordAudio:
        try:
            data = streamAudio.read(CHUNK)
            frames.append(data)
        except OSError:
            print('skipped audio frame')

        if len(frames) > 100:
           exportAudioFile(frames, nextAudioPath())
           frames = []
    #done recording
    exportAudioFile(frames, nextAudioPath())

def exportAudioFile(buffer, pathToExport):  
    print('exporting audio to ' + pathToExport)
    waveFile = wave.open(pathToExport, 'wb')
    waveFile.setnchannels(CHANNELS)
    waveFile.setsampwidth(audio.get_sample_size(FORMAT))
    waveFile.setframerate(RATE)
    waveFile.writeframes(b''.join(buffer))
    waveFile.close()

def finishRecordingVideo():
    global camera
    camera.stop_recording()

def finishRecordingAudio():
    global recordAudio
    recordAudio = False

def splitVideoToFile():
    global streamVideo
    global camera

    camera.split_recording('{0}after.h264'.format(path))
    thread.start_new_thread(copyToFile, ('{0}before.h264'.format(path),))

def stopLoopRecordAudio():
    pass

def copyToFile(pth):
    global PRE_RECORD_TIME
    streamVideo.copy_to(pth, seconds=PRE_RECORD_TIME)
    streamVideo.clear()

def button_down_callback(arg):
    global looping
    global hasAudio
    global continueProg
    global button_being_pressed
    
    if(GPIO.input(PIN_BUTTON) == 1):
        print('false input down')
        return
    button_being_pressed = True

    if looping:
        #stop looping and start recording
        splitVideoToFile()
        looping = False
        #setting looping to false stops the audio thread from loop recording
        #start audio, there is no audio on the before clip (flemme bro)
        if hasAudio:
            thread.start_new_thread(recordAudio, ())
        thread.start_new_thread(recordingSound, ())
        thread.start_new_thread(LED_recording_thread, ())
        
    else:
        #finish recording and exit
        finishRecordingVideo()
        if hasAudio:
            finishRecordingAudio()
        continueProg = False
        

setup()
try:
    surveilinge = False
    startTimee = 0
    while continueProg:
        if not surveilinge and button_being_pressed:
            #button just got pressed
            startTimee = time.time()
            surveilinge = True
            #print("button down time noted : %s" % startTimee)

        if surveilinge and GPIO.input(PIN_BUTTON) == 1:
            #button just got up
            #print("time diff : %s" % (time.time() - startTimee))
            surveilinge = False
            button_being_pressed = False
            if time.time() - startTimee > 2:
                finishRecordingVideo()
                if hasAudio:
                    finishRecordingAudio()
                shutdownSound()
                shutdown = True
                continueProg = False
        
finally:
    recordAudio = False
    try:
        camera.stop_recording()
    except:
        pass
    try:
        streamVideo.close()
    except:
        pass
    #end sound is also used to give the audio thread time to export and close
    if not shutdown:
        endSound()
    
    try:
        GPIO.cleanup()
    except:
        pass
    streamVideo.close()
    if hasAudio:
        streamAudio.stop_stream()
        streamAudio.close()
        audio.terminate()

    if shutdown:
        subprocess.call("halt")
    
    


