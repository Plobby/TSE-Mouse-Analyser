import cv2
import threading

import iomanager
import Segmentation as seg
import CCL

"""Function that processes a video stored at videoSource to find mouse in all frames of video. If the mouse cannot be found in a given frame, it is saved for later.
   The next time the mouse is found, that bounding box is also applied to all prior frames in which it was not found.
   After processing all frames, the bounding box is drawn on all frames and the video is returned."""
def processVideo(videoSource):
    #Dictionary containing bounding box locations for each frame (key = frame position)
    frameBoundingBoxes = {}
    #List of unprocessed frames, by frame position in video
    unprocessed = []
    #Threshold value to be applied to all frames, as calculated from the first frame
    videoThreshold = 0
    
    #Open the video stored at videoSource
    video = cv2.VideoCapture(videoSource)

    #Get first frame of video
    ret, frame = video.read()
    #Calculate threshold if a frame is returned (ret == true)
    if ret:
        videoThreshold = seg.otsuThreshold(frame)

    #Step through frames of video
    while video.isOpened():
        #Get frame number for current frame
        framePos = video.get(cv2.CAP_PROP_POS_FRAMES)
        #Calculate bounding box size for mouse in frame
        boundingBox = processFrame(frame, videoThreshold)

        #If a bounding box is not found, save frame for later
        if boundingBox == None:
            unprocessed.append(framePos)
        #Else use the bounding box of the current frame as the bounding box for any unprocessed frames before it
        else:
            while len(unprocessed) > 0:
                frameBoundingBoxes[unprocessed.pop(0)] = boundingBox   
            #Add current frame's bounding box to frameBoundingBoxes
            frameBoundingBoxes[framePos] = boundingBox

        #Get next frame of video and a flag indicating if there is a frame available
        ret, frame = video.read()
        #Break while loop if return flag is false
        if not ret:
            break
    
    mouseData = []

    #Draw bounding box on to each frame of video and calculate com, width & height
    for key, box in frameBoundingBoxes.items(): #Box contains [MinimumX, MaximumX, MinimumY, MaximumY] values for bounding box
        #Set frame position
        video.set(cv2.CAP_PROP_POS_FRAMES, key)
        #Get frame
        ret, frame = video.read()

        #Draw bounding box using box values
        if ret:
            #Draw sides
            for x in range(box[0], box[1] + 1):
                frame[x, box[2]] = [255, 0, 0]
                frame[x, box[3]] = [255, 0, 0]

            #Draw top and bottom
            for y in range(box[2], box[3] + 1):
                frame[box[0], y] = [255, 0, 0]
                frame[box[1], y] = [255, 0, 0]

        else:
            break

        #Find width of mouse
        mouseWidth = box[3] - box[2]
        #Find height of mouse
        mouseHeight = box[1] - box[0]
        #Find centre of mass of mouse
        mouseCOM = (box[2] + (mouseWidth / 2), box[0] + (mouseHeight / 2))

        #Add mouse data to mouseData (conventional coordinates i.e. (0,0) = bottom left corner)
        mouseData.append([mouseCOM, mouseWidth, mouseHeight])

    #Save video to user's desired location
    iomanager.save_videos([video], None)

    return video, mouseData

"""Function that attempt to find the mouse in a frame. If no mouse cannot be clearly found, return None. Else, return bounding box min and max values"""
def processFrame(frame, threshold):
     #Create segmented version of frame
    segmented = seg.thresholdSegment(frame, threshold)
    #Find all objects in segmented frame using CCL
    objects = CCL.CCL(segmented)
    
    #Create array to hold sorted objects keys
    sortedKeys = []
    
    #Sort keys of objects in reverse order by length of array associated with each key
    for key in sorted(objects, key=lambda k: len(objects[k]), reverse=True):
        sortedKeys.append(key) 
    
    #Set targetObject to the 2nd largest object in frame (assuming feed station is largest, mouse 2nd largest)
    targetObject = sortedKeys[1]
    
    #Find extreme pixels in target object
    MinX = frame.shape[0]
    MaxX = 0
    MinY = frame.shape[1]
    MaxY = 0

    for coord in objects[targetObject]:
        if coord[0] < MinX:
            MinX = coord[0]
        if coord[0] > MaxX:
            MaxX = coord[0]
        if coord[1] < MinY:
            MinY = coord[1]
        if coord[1] > MaxY:
            MaxY = coord[1]

    return MinX, MaxX, MinY, MaxY

    