import torch
import cv2
#import onnx
import os
import sys
import time
from torchvision import transforms
from PIL import Image
import pycuda.driver as cuda
import pycuda.autoinit
import numpy as np
import tensorrt as trt
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import depthai
import threading
import warnings
warnings.filterwarnings("ignore",category=DeprecationWarning)

engine_precision='FP16'
#img_size = [3, 480, 640] # for NYUv2
img_size = [3, 352, 1216] # for kitti
#img_size = [3, 192, 640] # for kitti from lenovo frame of size (480,640)
batch_size=1
dataset = "kitti" #"kitti" or "nyu" 
min_depth_eval = 1e-3
max_depth_eval = 80 if dataset == 'kitti' else 10
TRT_LOGGER = trt.Logger()

def get_image_path_lists(rgb_path, gt_depth_path, data_splits_file_path):
    with open(data_splits_file_path,'r') as f:
        filenames = f.readlines()
    rgb_path_list = []
    gt_depth_path_list = []
    for line in filenames:
        rgb_file = line.split()[0]
        if dataset == "kitti":
            depth_file = os.path.join(line.split()[0].split('/')[0], line.split()[1])
        else:
            depth_file = line.split()[1]

        rgb_path_list.append(os.path.join(rgb_path,rgb_file))
        gt_depth_path_list.append(os.path.join(gt_depth_path,depth_file))
    return rgb_path_list, gt_depth_path_list

def live_preprocess_image(image):
    #image = np.asarray(Image.open(img_path), dtype=np.float32) / 255.0
    image = image / 255.0
    image = torch.from_numpy(image.transpose((2, 0, 1)))
    normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    image = normalize(image)
    return image


def colorize(depth,cmap, vmin=None,vmax=None):
    vmin = depth.min() if vmin is None else vmin
    vmax = depth.max() if vmax is None else vmax

    depth = np.clip(depth,vmin,vmax)
    #depth = 1/depth
    colormap = cm.get_cmap(cmap)
    colored_depth = colormap((depth-vmin)/(vmax-vmin)) #first convert from 0-1 then from 0-255 in below line.
    #colored_depth = colormap(depth)
    colored_depth_rgb = (colored_depth[:,:,:3]*255).astype(np.uint8)
    return colored_depth_rgb

def get_scale_shift(prediction, target,  min_depth, max_depth):
    """Returns the median scaling factor from gt_depth and pred_depth,
        Tells by what scale factor you should scale up(multipy) your pred_depth.
    """
    mask = np.logical_and(target>min_depth , target<max_depth)
    scale = np.median(target[mask]) / np.median(prediction[mask])
    return scale

import threading
import cv2

# Define the thread that will continuously pull frames from the camera
# class CameraBufferCleanerThread(threading.Thread):
#     def __init__(self, camera, name='camera-buffer-cleaner-thread'):
#         self.camera = camera
#         self.last_frame = None
#         super(CameraBufferCleanerThread, self).__init__(name=name)
#         self.start()

#     def run(self):
#         while True:
#             ret, self.last_frame = self.camera.read()
# Global variables
frame = None
is_frame_available = False
stop_capture = threading.Event()  # Event object to signal stop

# Function to continuously capture frames
def capture_frames():
    global frame, is_frame_available

    # Create the pipeline and camera node
    pipeline = depthai.Pipeline()
    cam = pipeline.createColorCamera()
    cam.setPreviewSize(1280,720)
    cam.setResolution(depthai.ColorCameraProperties.SensorResolution.THE_1080_P)
    #cam.setResolution(depthai.ColorCameraProperties.SensorResolution.THE_4_K)
    #cam.setResolution(depthai.ColorCameraProperties.SensorResolution.THE_12_MP)
    #cam.initialControl.setManualFocus(140) # 0..255 (larger for near objects)
    # Focus: 
    # value 150 == 22cm 
    # value 140 == 36cm
    # value 
    xoutRgb = pipeline.createXLinkOut()
    xoutRgb.setStreamName("rgb")
    cam.video.link(xoutRgb.input)

    # Start the pipeline
    with depthai.Device(pipeline) as device:
        # Output queue for the frames
        q_rgb = device.getOutputQueue(name="rgb", maxSize=1, blocking=False)

        while not stop_capture.is_set():
            # Get the RGB frame
            in_rgb = q_rgb.tryGet()

            if in_rgb is not None:
                # Convert the NV12 format to BGR
                frame = in_rgb.getCvFrame()

                # Set the flag to indicate that a new frame is available
                is_frame_available = True


def tensorrt_inference(tensorrt_engine_path):
    
    a = time.time()
    trt.init_libnvinfer_plugins(None, "")
    with open(tensorrt_engine_path, "rb") as f, trt.Runtime(TRT_LOGGER) as runtime: 
        engine = runtime.deserialize_cuda_engine(f.read()) 
    b = time.time()
    print(f"Took {(b-a):.2f} seconds for loading model!!")
    context = engine.create_execution_context()

    for binding in engine:
        if engine.binding_is_input(binding):  
            input_shape = engine.get_binding_shape(binding)
            input_size = trt.volume(input_shape) * engine.max_batch_size * np.dtype(np.float32).itemsize  
            device_input = cuda.mem_alloc(4*input_size)
        else:  
            output_shape = engine.get_binding_shape(binding)
            host_output = cuda.pagelocked_empty(trt.volume(output_shape) * engine.max_batch_size, dtype=np.float32)
            device_output = cuda.mem_alloc(4*host_output.nbytes)

    stream = cuda.Stream()

    # Create a VideoCapture object to read from the webcam (index 0)
    # cap = cv2.VideoCapture(0)
    #cam_cleaner = CameraBufferCleanerThread(cap)

    # Check if the webcam is successfully opened
    # if not cap.isOpened():
    #     print("Failed to open webcam")
    #     exit()

    start_time = time.time()
    idx=0
    global frame, is_frame_available
    while True:
        global_idx = idx+1
        # Read a frame from the webcam
        #ret, image = cap.read()
        
        while not is_frame_available:
            pass
        #print(frame.shape)
        #"""
        image = frame.copy()
        if dataset == "kitti": # do kb_crop
            top_margin = 525
            left_margin = 0
            image = image[top_margin:top_margin + 1110, left_margin:left_margin + 3840]
            image = cv2.resize(image,(img_size[2],img_size[1]))
        data = live_preprocess_image(image)
        
        host_input = np.array(data, dtype=np.float32, order='C')
        cuda.memcpy_htod_async(device_input, host_input, stream)

        context.execute_async(bindings=[int(device_input), int(device_output)], stream_handle=stream.handle)
        cuda.memcpy_dtoh_async(host_output, device_output, stream)
        stream.synchronize()

        output_data = torch.Tensor(host_output).reshape(engine.max_batch_size, img_size[1], img_size[2])
        pred_depth = output_data.cpu().numpy().squeeze()

        # if dataset == "kitti": # do kb_crop
        #     height = image.shape[0]
        #     width = image.shape[1]
        #     top_margin = int(height - 352)
        #     left_margin = int((width - 1216) / 2)
        #     # depth_gt = depth_gt.crop((left_margin, top_margin, left_margin + 1216, top_margin + 352))
        #     # image = image.crop((left_margin, top_margin, left_margin + 1216, top_margin + 352))
        #     gt_depth = gt_depth[top_margin:top_margin + 352, left_margin:left_margin + 1216]
        #     image = image[top_margin:top_margin + 352, left_margin:left_margin + 1216]

        # pred_depth[pred_depth < min_depth_eval] = min_depth_eval
        # pred_depth[pred_depth > max_depth_eval] = max_depth_eval
        # pred_depth[np.isinf(pred_depth)] = max_depth_eval
        # pred_depth[np.isnan(pred_depth)] = min_depth_eval
        
        # scale = get_scale_shift(pred_depth, gt_depth, min_depth=min_depth_eval, max_depth=max_depth_eval )
        # #print(f"scale = {scale}")
        # pred_depth = pred_depth*scale

        # pred_depth[gt_depth==0] = 0
        #vmax = max(np.max(pred_depth),np.max(gt_depth))
        #vmax=80.0
        #print("vmax = ",vmax)
        cmap='inferno' #'magma', 'inferno'
        #gt_depth = colorize(gt_depth, cmap=cmap, vmin=0, vmax=vmax)
        print(f"min = {np.min(pred_depth), np.max(pred_depth)}")
        pred_depth = colorize(pred_depth, cmap=cmap,vmin = 0,vmax=8)
        #sys.exit(0)
        thickness=2
        
        cv2.rectangle(image,(0,0), (190,35), (0,0,0),-1)
        cv2.rectangle(pred_depth,(0,0), (270,35), (0,0,0),-1)
        cv2.putText(image,"RGB Image",(5,25), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), thickness, cv2.LINE_AA)
        #cv2.putText(gt_depth,"Groundtruth depth",(10,20), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), thickness, cv2.LINE_AA)
        cv2.putText(pred_depth,"Predicted depth",(5,25), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), thickness, cv2.LINE_AA)
        print(image.shape, pred_depth.shape)
        combined = np.vstack((image,pred_depth))

        window_name = "Pixelformer Depth Prediction"    

        cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        #cv2.resizeWindow(window_name, 1800,1000)

        #cv2.imwrite(f"sample_output_images/kitti/{idx:03d}.png",combined)
        cv2.imshow(window_name, combined)
        idx+=1
        #"""
        #key = cv2.waitKey(1)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            stop_capture.set()  # Set the stop signal
            break
        

    cv2.destroyAllWindows()
    #cap.release()
    end_time = time.time()
    print(f"Took {end_time-start_time:.2f} seconds for {global_idx} images!!")
    #print(f"{len(rgb_path_list)/(end_time-start_time)} FPS")
    print(f"{global_idx/(end_time-start_time)} FPS")
    print(f"Took {end_time-a:.2f} seconds from start!!")
    
    #plt.imsave("pred_depth_tensorrt.png",pred_depth,cmap="magma",vmin=0,vmax=3)


if __name__ == '__main__':
    onnx_model_path = "/home/vision/suraj/jetson-documentation/model_compression/onnx_models/from_vision04/kitti_model-55000-best_abs_rel_0.05135.onnx"
    tensorrt_engine_path = os.path.join("tensorRT_engines",os.path.basename(onnx_model_path)[:-5]+".trt")
    tensorrt_engine_path = "/home/vision/suraj/jetson-documentation/model_compression/tensorRT_engines/nyu_model-64000-best_abs_rel_0.09021.trt"
    tensorrt_engine_path = "/home/vision/suraj/jetson-documentation/model_compression/tensorRT_engines/kitti_model-55000-best_abs_rel_0.05135.trt"
    #convert onnx to tensorRT
    # if not os.path.exists(tensorrt_engine_path):
    #     build_engine(onnx_model_path, tensorrt_engine_path, engine_precision, img_size, batch_size)

    # Start the frame capture thread
    capture_thread = threading.Thread(target=capture_frames)
    capture_thread.start()
    
    #inference tensorrt
    tensorrt_inference(tensorrt_engine_path)

    # Wait for the frame capture thread to finish
    capture_thread.join()

    # Close the OpenCV windows
    cv2.destroyAllWindows()
        


