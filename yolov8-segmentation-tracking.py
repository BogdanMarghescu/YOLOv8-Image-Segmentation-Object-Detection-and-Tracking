import cv2
import json
import numpy as np
from ultralytics import YOLO
from ultralytics.yolo.engine.results import Results
from _collections import deque
from deep_sort_realtime.deepsort_tracker import DeepSort

# colors for visualization for image visualization
COLORS = [(56, 56, 255), (151, 157, 255), (31, 112, 255), (29, 178, 255), (49, 210, 207), (10, 249, 72), (23, 204, 146),
          (134, 219, 61), (52, 147, 26), (187, 212, 0), (168, 153, 44), (255, 194, 0), (147, 69, 52), (255, 115, 100),
          (236, 24, 0), (255, 56, 132), (133, 0, 82), (255, 56, 203), (200, 149, 255), (199, 55, 255)]


def result_to_json(result: Results, tracker=None):
    """
    Convert result from ultralytics YOLOv8 prediction to json format
    Parameters:
        result: Results from ultralytics YOLOv8 prediction
        tracker: DeepSort tracker
    Returns:
        result_list_json: detection result in json format
    """
    result_list_json = [
        {
            'class_id': int(result.boxes.cls[idx]),
            'class': result.names[int(result.boxes.cls[idx])],
            'confidence': float(result.boxes.conf[idx]),
            'bbox': {
                'x_min': int(result.boxes.boxes[idx][0]),
                'y_min': int(result.boxes.boxes[idx][1]),
                'x_max': int(result.boxes.boxes[idx][2]),
                'y_max': int(result.boxes.boxes[idx][3]),
            },
            'mask': cv2.resize(result.masks.data[idx].cpu().numpy(), (result.orig_shape[1], result.orig_shape[0])).tolist(),
            'segments': result.masks.segments[idx].tolist(),
        } for idx in range(len(result))
    ]
    if tracker is not None:
        bbs = [
            (
                [
                    result_list_json[idx]['bbox']['x_min'],
                    result_list_json[idx]['bbox']['y_min'],
                    result_list_json[idx]['bbox']['x_max'] - result_list_json[idx]['bbox']['x_min'],
                    result_list_json[idx]['bbox']['y_max'] - result_list_json[idx]['bbox']['y_min']
                ],
                result_list_json[idx]['confidence'],
                result_list_json[idx]['class'],
            ) for idx in range(len(result))
        ]
        tracks = tracker.update_tracks(bbs, frame=result.orig_img)
        for idx in range(len(result_list_json)):
            track_idx = next((i for i, track in enumerate(tracks) if track.det_conf is not None and np.isclose(track.det_conf, result_list_json[idx]['confidence'])), -1)
            if track_idx != -1:
                result_list_json[idx]['object_id'] = int(tracks[track_idx].track_id)
    return result_list_json


def view_result_ultralytics(result: Results, result_list_json, centers=None):
    """
    Visualize result from ultralytics YOLOv8 prediction using ultralytics YOLOv8 built-in visualization function
    Parameters:
        result: Results from ultralytics YOLOv8 prediction
        result_list_json: detection result in json format
        centers: list of deque of center points of bounding boxes
    Returns:
        result_image_ultralytics: result image from ultralytics YOLOv8 built-in visualization function
    """
    result_cpu = result.cpu()
    result_cpu.names = result.names
    result_image_ultralytics = result_cpu.visualize()
    for result in result_list_json:
        class_color = COLORS[result['class_id'] % len(COLORS)]
        if 'object_id' in result and centers is not None:
            centers[result['object_id']].append((int((result['bbox']['x_min'] + result['bbox']['x_max']) / 2), int((result['bbox']['y_min'] + result['bbox']['y_max']) / 2)))
            for j in range(1, len(centers[result['object_id']])):
                if centers[result['object_id']][j - 1] is None or centers[result['object_id']][j] is None:
                    continue
                thickness = int(np.sqrt(64 / float(j + 1)) * 2)
                cv2.line(result_image_ultralytics, centers[result['object_id']][j - 1], centers[result['object_id']][j], class_color, thickness)
    return result_image_ultralytics


def view_result_default(result: Results, result_list_json, centers=None):
    """
    Visualize result from ultralytics YOLOv8 prediction using default visualization function
    Parameters:
        result: Results from ultralytics YOLOv8 prediction
        result_list_json: detection result in json format
        centers: list of deque of center points of bounding boxes
    Returns:
        result_image_default: result image from default visualization function
    """
    ALPHA = 0.5
    image = result.orig_img
    for result in result_list_json:
        class_color = COLORS[result['class_id'] % len(COLORS)]
        image_mask = np.stack([np.array(result['mask']) * class_color[0], np.array(result['mask']) * class_color[1], np.array(result['mask']) * class_color[2]], axis=-1).astype(np.uint8)
        image = cv2.addWeighted(image, 1, image_mask, ALPHA, 0)
        text = f"{result['class']} {result['object_id']}: {result['confidence']:.2f}" if 'object_id' in result else f"{result['class']}: {result['confidence']:.2f}"
        cv2.rectangle(image, (result['bbox']['x_min'], result['bbox']['y_min']), (result['bbox']['x_max'], result['bbox']['y_max']), class_color, 2)
        (text_width, text_height), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
        cv2.rectangle(image, (result['bbox']['x_min'], result['bbox']['y_min'] - text_height - baseline), (result['bbox']['x_min'] + text_width, result['bbox']['y_min']), class_color, -1)
        cv2.putText(image, text, (result['bbox']['x_min'], result['bbox']['y_min'] - baseline), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
        if 'object_id' in result and centers is not None:
            centers[result['object_id']].append((int((result['bbox']['x_min'] + result['bbox']['x_max']) / 2), int((result['bbox']['y_min'] + result['bbox']['y_max']) / 2)))
            for j in range(1, len(centers[result['object_id']])):
                if centers[result['object_id']][j - 1] is None or centers[result['object_id']][j] is None:
                    continue
                thickness = int(np.sqrt(64 / float(j + 1)) * 2)
                cv2.line(image, centers[result['object_id']][j - 1], centers[result['object_id']][j], class_color, thickness)
    return image


def image_processing(frame, model, image_viewer=view_result_default, tracker=None, centers=None):
    """
    Process image frame using ultralytics YOLOv8 model and possibly DeepSort tracker if it is provided
    Parameters:
        frame: image frame
        model: ultralytics YOLOv8 model
        image_viewer: function to visualize result, default is view_result_default, can be view_result_ultralytics
        tracker: DeepSort tracker
        centers: list of deque of center points of bounding boxes
    Returns:
        result_image: result image with bounding boxes, class names, confidence scores, object masks, and possibly object IDs
        result_list_json: detection result in json format
    """
    results = model.predict(frame)
    result_list_json = result_to_json(results[0], tracker=tracker)
    result_image = image_viewer(results[0], result_list_json, centers=centers)
    return result_image, result_list_json


# Model initialization
model = YOLO('yolov8s-seg.pt')

# YOLOv8S-SEGMENTATION - IMAGE
IMAGE_PATH = "images/family-and-dog.jpg"
image = cv2.imread(IMAGE_PATH)
image, result_list_json = image_processing(image, model)
# print(json.dumps(result_list_json, indent=2))
cv2.imshow(f"Image - Source: {IMAGE_PATH}", image)
cv2.waitKey(0)

# YOLOv8S-SEGMENTATION-TRACKING - REAL-TIME CAMERA
CAM_ID = 0
cam = cv2.VideoCapture(CAM_ID)
cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
tracker = DeepSort(max_age=5)
centers = [deque(maxlen=30) for _ in range(10000)]
while True:
    _, image = cam.read()
    image, result_list_json = image_processing(image, model, tracker=tracker, centers=centers)
    # print(json.dumps(result_list_json, indent=2))
    cv2.imshow(f"Video Stream - Source: {CAM_ID}", image)
    if cv2.waitKey(1) == 27:  # ESC
        break
cam.release()
cv2.destroyAllWindows()
tracker.delete_all_tracks()
centers.clear()