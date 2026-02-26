import os
import csv
import json
import time
import shutil
import pathlib
from datetime import datetime
try:
    import numpy as np
    import pandas as pd
    from ultralytics import YOLO
    import cv2
except ModuleNotFoundError:
    import subprocess, sys
    subprocess.check_call(sys.executable, '-m', 'pip', 'install', 'opencv-python', 'pandas', 'numpy', 'ultralytics')
    import cv2
    import numpy as np
    import pandas as pd
    from ultralytics import YOLO

models_bl_dict = {
        'Best': {
                    'night':'Model/finetune_mdv6_yolov10_3101_night2/weights/best.pt',
                    'day':  'Model/finetune_mdv6_yolov10_2001_day/weights/best.pt'
                },
        'Last': {
                    'night':'Model/finetune_mdv6_yolov10_3101_night2/weights/last.pt',
                    'day':  'Model/finetune_mdv6_yolov10_2001_day/weights/last.pt'
                }
        }

colour = (
    (0, 0, 255),      # Red
    (0, 255, 0),      # Green
    (255, 0, 0),      # Blue
    (0, 255, 255),    # Yellow
    (255, 0, 255),    # Magenta
    (255, 255, 0),    # Cyan
    (0, 128, 255),    # Orange
    (128, 0, 128),    # Purple
    (0, 255, 128),    # Spring Green
    (255, 128, 0),    # Azure
    (0, 0, 128),      # Dark Red
    (0, 128, 0),      # Dark Green
    (128, 0, 0),      # Dark Blue
    (128, 128, 0),    # Dark Cyan
    (0, 128, 128),    # Olive
    (128, 0, 255),    # Pink / Hot Pink
    (255, 0, 128),    # Light Blue
    (192, 192, 192),  # Silver
    (0, 69, 255),     # Dark Orange
    (144, 238, 144),  # Light Green
)

class app():
    def __init__(self,
                 model: str,
                 input_path: str,
                 output_path: str,
                 output_mode: str,
                 day_conf: float,
                 night_conf: float,
                 progress_callback=None,
                 verbose: bool = False):
        self.start_time = time.perf_counter()
        self.timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.verbose = verbose
        self.model = models_bl_dict[model]
        self.day_model = YOLO(self.model['day'])
        self.day_model.to("cuda")
        self.day_conf = day_conf/100
        self.night_model = YOLO(self.model['night'])
        self.night_model.to("cuda")
        self.night_conf = night_conf/100
        self.IMAGE_DIR = input_path
        self.output_dir = output_path
        self.output_mode = output_mode
        self.progress_callback = progress_callback
        self.OUTPUT_JSON = os.sep.join([self.output_dir,
                                        f"results_{self.timestamp} CONF {int(self.day_conf*100)}-{int(self.night_conf*100)} MODEL {model} MODE {self.output_mode}.json"])
        self.OUTPUT_XLSX = os.sep.join([self.output_dir,
                                        f"results_{self.timestamp} CONF {int(self.day_conf*100)}-{int(self.night_conf*100)} MODEL {model} MODE {self.output_mode}.xlsx"])
        self.DETECTED_DIR = os.sep.join([self.output_dir,
                                         f"has_animal_{self.timestamp} CONF {int(self.day_conf*100)}-{int(self.night_conf*100)} MODEL {model} MODE {self.output_mode}"])
        self.UNDETECTED_DIR = os.sep.join([self.output_dir,
                                           f"no_animal_{self.timestamp} CONF {int(self.day_conf*100)}-{int(self.night_conf*100)} MODEL {model}"])
        for path in [self.output_dir, self.DETECTED_DIR, self.UNDETECTED_DIR]:
            p = pathlib.Path(path)
            assert p.is_file() == False
            if p.is_dir():
                print(p,'is dir, skipping')
                pass
            else:
                print(f'creating DIR {p}')
                os.mkdir(path)

    def is_night_by_color(self, img, color_thresh=10):
        # img: BGR (OpenCV)
        b, g, r = cv2.split(img)
        diff_rg = np.mean(np.abs(r - g))
        diff_rb = np.mean(np.abs(r - b))
        diff_gb = np.mean(np.abs(g - b))
        color_score = (diff_rg + diff_rb + diff_gb) / 3
        return color_score < color_thresh, color_score


    def run_detection(self, img_path, day_model, night_model, ):
        img = cv2.imread(img_path)
        if img is None:
            return None
        # === determine scene ===
        is_night, color_score = self.is_night_by_color(img, color_thresh=10)
        if is_night:
            '''self.enhance_contrast_clahe(img)'''
            img_for_infer = img
            model = night_model
            infer_iou = 0.85
            scene = "night"
            CONF_THRESHOLD = self.night_conf
        else:
            img_for_infer = img
            model = day_model
            infer_iou = 0.75
            scene = "day"
            CONF_THRESHOLD = 0.15
        # === Keep all the box ===
        out = model(img_for_infer, conf=0.001, iou=infer_iou,verbose=False)[0]
        boxes = out.boxes
        # === Get confidence ===
        if boxes is not None and boxes.conf is not None:
            conf_list = [float(c) for c in boxes.conf.cpu().tolist()]
        else:
            conf_list = []
        return {
            "scene": scene,
            "conf_list": conf_list,
            "threshold": CONF_THRESHOLD,
            "img": img,
            "boxes": boxes
        }

    def enhance_contrast_clahe(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        clahe = cv2.createCLAHE(
            clipLimit=2.5,
            tileGridSize=(8, 8)
        )
        enhanced = clahe.apply(gray)

        enhanced_bgr = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
        return enhanced_bgr

    def write_image(self, opath, det):
        animal_count = sum(c > det['threshold'] for c in det['conf_list'])
        boxes = [[det['conf_list'][i], det['boxes'][i]] for i, j in enumerate(det['conf_list']) if j > det['threshold']]
        img = det['img']
        try:
            assert animal_count < 20
        except AssertionError:
            animal_count = 0
            if self.verbose: print(f"{opath.split(os.sep)[0]} contains too many animals {animal_count} likely error")
        if self.output_mode == 'Original images' or animal_count == 0:
            cv2.imwrite(opath, img)
            #shutil.copy(ipath, opath)
        elif self.output_mode == 'Annotated images':
            for index, j in enumerate(boxes):
                conf, box = j
                conf = format(conf*100,'.0f') + '%'
                tl, tr, bl, br = map(int, box.xyxy[0])
                # This will fail if there are more than 20 animals
                cv2.rectangle(img, (tl,tr), (bl,br), colour[index], 2)
                cv2.putText(img, str(conf), (tl, tr-10), cv2.FONT_HERSHEY_SIMPLEX, 2.5, colour[index], 2)
            cv2.imwrite(opath, img)

    def main(self):
        results = []
        json_results = {}
        if self.verbose: print("\nStart detecting images...\n")
        images = [i for i in os.listdir(self.IMAGE_DIR) if i.lower().endswith((".jpg", ".jpeg", ".png"))]
        total = len(images)
        cbstatus = self.progress_callback is not None
        counts = {'has animals':0, 'no animals':0}
        #if self.verbose:
        print(f"callback is {self.progress_callback}")
        for index, filename in enumerate(images):
            path = os.sep.join([self.IMAGE_DIR, filename])

            det = self.run_detection(path, self.day_model, self.night_model)
            if det is None:
                continue

            conf_list = det["conf_list"]
            scene = det["scene"]
            CONF_THRESHOLD = det["threshold"]
            boxes = det["boxes"]
            animal_count = sum(c > CONF_THRESHOLD for c in conf_list)
            max_conf = max(conf_list) if conf_list else 0.0
            if animal_count > 0:
                self.write_image(os.path.join(self.DETECTED_DIR, filename), det)
                counts['has animals'] += 1
                if self.verbose: print(f"{filename} does not contain animals")
            else:
                self.write_image(os.path.join(self.UNDETECTED_DIR, filename), det)
                counts['no animals'] += 1
                if self.verbose: print(f"{filename} does not contain animals")
                if self.verbose: print(f"{filename} contains animals")
            if cbstatus:
                self.progress_callback(index+1, total)

            # === JSON ===
            json_results[filename] = {
                "scene": scene,
                "animals_above_threshold": int(animal_count),
                "max_confidence": max_conf
            }

            results.append([
                filename,
                scene,
                int(animal_count),
                max_conf
            ])
        # JSON file
        with open(self.OUTPUT_JSON, "w") as f:
            json.dump(json_results, f, indent=4)

        df = pd.DataFrame(
            results,
            columns=["image_name", "scene", "animals_detected", "max_confidence"]
        )

        df.to_excel(self.OUTPUT_XLSX, index=False)
        has_animal_percentage = format((counts['has animals']/total)*100, '.0f')
        no_animal_percentage = format((counts['no animals']/total)*100, '.0f')
        duration = format(time.perf_counter() - self.start_time, '.0f')
        message = f"""Completed in {duration} seconds
Wrote JSON, Excel Spreadsheet and Sorted images
Images containing animals: {counts['has animals']} ({has_animal_percentage}%)
Images without animals: {counts['no animals']} ({no_animal_percentage}%)

Result timestamp: {self.timestamp}
Images saved to folder
{self.output_dir}"""
        return message

