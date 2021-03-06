#!/usr/bin/python

import cv_bridge
import cv2
import dlib
import threading
import time
import sys
import rospy
import numpy as np
import baxter_interface
import rospkg
import os
from baxter_interface import CHECK_VERSION
from lab_baxter_common.camera_toolkit.camera_control_helpers import CameraController

from sensor_msgs.msg import(
    Image
)

rospack = rospkg.RosPack()
cascPath = os.path.join(rospack.get_path("baxter_general_toolkit"), 'python_src/lab_baxter_common/face_id/opencv-3.4.1/data/haarcascades/haarcascade_frontalface_default.xml')
faceCascade = cv2.CascadeClassifier(cascPath)
video_capture = cv2.VideoCapture(0)

OUTPUT_SIZE_WIDTH = 960
OUTPUT_SIZE_HEIGHT = 600

class CameraNode:
    def __init__(self):
        self._head_sub = rospy.Subscriber('/cameras/head_camera/image', Image, self._head_cb, queue_size=1)
        self._last_image = None
        self._settings = CameraController.createCameraSettings(width=1280, height=800, exposure=-1)
        CameraController.openCameras("head_camera", settings=self._settings)

        #Create two opencv named windows
        #cv2.namedWindow("base-image", cv2.WINDOW_AUTOSIZE)
        cv2.namedWindow("Head Camera Video Feed", cv2.WINDOW_AUTOSIZE)

        #Position the windows next to eachother
        #cv2.moveWindow("base-image",0,100)
        cv2.moveWindow("Head Camera Video Feed", 0, 100)

        #Start the window thread for the two windows we are using
        cv2.startWindowThread()

        #The color of the rectangle we draw around the face
        self.rectangleColor = (0,165,255)

        #variables holding the current frame number and the current faceid
        self.frameCounter = 0
        self.currentFaceID = 0

        #Variables holding the correlation trackers and the name per faceid
        self.faceTrackers = {}
        self.faceNames = {}
        
    def _head_cb(self, msg):
        self._last_image = msg
        
    #We are not doing really face recognition
    def doRecognizePerson(self, faceNames, fid):
        time.sleep(2)
        faceNames[ fid ] = "Person " + str(fid)

    def detect(self):  
        head = baxter_interface.Head()
        head.set_pan(0)
        try:
            while True:
                # Capture frame-by-frame
                if self._last_image != None:
                    frame = cv_bridge.CvBridge().imgmsg_to_cv2(self._last_image, desired_encoding='bgr8')
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                    faces = faceCascade.detectMultiScale(
                        gray,
                        scaleFactor=1.1,
                        minNeighbors=5,
                        minSize=(30, 30),
                        flags=cv2.CASCADE_SCALE_IMAGE
                    )

                    resultImage = frame.copy()
                    self.frameCounter += 1 
                    
                fidsToDelete = []
                for fid in self.faceTrackers.keys():
                    trackingQuality = self.faceTrackers[ fid ].update( frame )

                    #If the tracking quality is good enough, we must delete
                    #this tracker
                    if trackingQuality < 8:
                        fidsToDelete.append( fid )

                for fid in fidsToDelete:
                    print("Removing fid " + str(fid) + " from list of trackers")
                    self.faceTrackers.pop( fid , None )
                                
                #if (self.frameCounter % 10) == 0:

                #Loop over all faces and check if the area for this
                #face is the largest so far
                #We need to convert it to int here because of the
                #requirement of the dlib tracker. If we omit the cast to
                #int here, you will get cast errors since the detector
                #returns numpy.int32 and the tracker requires an int
                for (_x,_y,_w,_h) in faces:
                    x = int(_x)
                    y = int(_y)
                    w = int(_w)
                    h = int(_h)


                    #calculate the centerpoint
                    x_bar = x + 0.5 * w
                    y_bar = y + 0.5 * h



                    #Variable holding information which faceid we 
                    #matched with
                    matchedFid = None

                    #Now loop over all the trackers and check if the 
                    #centerpoint of the face is within the box of a 
                    #tracker
                    for fid in self.faceTrackers.keys():
                        tracked_position =  self.faceTrackers[fid].get_position()

                        t_x = int(tracked_position.left())
                        t_y = int(tracked_position.top())
                        t_w = int(tracked_position.width())
                        t_h = int(tracked_position.height())


                        #calculate the centerpoint
                        t_x_bar = t_x + 0.5 * t_w
                        t_y_bar = t_y + 0.5 * t_h

                        #check if the centerpoint of the face is within the 
                        #rectangleof a tracker region. Also, the centerpoint
                        #of the tracker region must be within the region 
                        #detected as a face. If both of these conditions hold
                        #we have a match
                        if ( ( t_x <= x_bar   <= (t_x + t_w)) and 
                             ( t_y <= y_bar   <= (t_y + t_h)) and 
                             ( x   <= t_x_bar <= (x   + w  )) and 
                             ( y   <= t_y_bar <= (y   + h  ))):
                            matchedFid = fid


                    #If no matched fid, then we have to create a new tracker
                    if matchedFid is None:

                        print("Creating new tracker " + str(self.currentFaceID))

                        #Create and store the tracker 
                        tracker = dlib.correlation_tracker()
                        tracker.start_track(frame,
                                            dlib.rectangle( x-10,
                                                            y-20,
                                                            x+w+10,
                                                            y+h+20))

                        self.faceTrackers[ self.currentFaceID ] = tracker

                        #Start a new thread that is used to simulate 
                        #face recognition. This is not yet implemented in this
                        #version :)
                        t = threading.Thread( target = self.doRecognizePerson ,
                                               args=(self.faceNames, self.currentFaceID))
                        t.start()

                        #Increase the currentFaceID counter
                        self.currentFaceID += 1




                #Now loop over all the trackers we have and draw the rectangle
                #around the detected faces. If we 'know' the name for this person
                #(i.e. the recognition thread is finished), we print the name
                #of the person, otherwise the message indicating we are detecting
                #the name of the person
                
                length = len(self.faceTrackers)
                for fid in self.faceTrackers.keys():
                    tracked_position =  self.faceTrackers[fid].get_position()
                    t_x = int(tracked_position.left())
                    t_y = int(tracked_position.top())
                    t_w = int(tracked_position.width())
                    t_h = int(tracked_position.height())
                    
                    cv2.rectangle(resultImage, (t_x, t_y),
                                            (t_x + t_w , t_y + t_h),
                                            self.rectangleColor ,2)


                    if fid in self.faceNames.keys():
                        cv2.putText(resultImage, self.faceNames[fid] , 
                                    (int(t_x + t_w/2), int(t_y)), 
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.5, (255, 255, 255), 2)
                    else:
                        cv2.putText(resultImage, "Detecting..." , 
                                    (int(t_x + t_w/2), int(t_y)), 
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.5, (255, 255, 255), 2)
                                    
                if length != 0:
                    num = min(self.faceTrackers)
                    x = self.faceTrackers[num].get_position().left()
                    if x != 0:
                        if x < 350:
                            head.set_pan(head.pan() + 0.25) 
                        elif x < 570:
                            head.set_pan(head.pan() + 0.15)
                        if x > 850:
                            head.set_pan(head.pan() - 0.25)
                        elif x > 630:
                            head.set_pan(head.pan() - 0.15)

                largeResult = cv2.resize(resultImage, (OUTPUT_SIZE_WIDTH,OUTPUT_SIZE_HEIGHT))
                cv2.imshow("Head Camera Video Feed", largeResult)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
        except KeyboardInterrupt as e:
            pass
                
        # When everything is done, release the capture
        video_capture.release()
        cv2.destroyAllWindows()
            
if __name__ == '__main__' :
    rospy.init_node("face")
    cn = CameraNode()
    cn.detect()
