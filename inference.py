from yoloface import yolov5
from model import FullGenerator
from skimage import transform as trans
from torch.nn import functional as F

import torch
import cv2 
import argparse
import numpy as np


def crop_with_ldmk(img, ldmk):
    std_ldmk = np.array([[193, 240], [319, 240],
                         [257, 314], [201, 371],
                         [313, 371]], dtype=np.float32) / 2
    tform = trans.SimilarityTransform()
    tform.estimate(ldmk, std_ldmk)
    M = tform.params[0:2, :]
    cropped = cv2.warpAffine(img, M, (256, 256), borderValue=0.0)
    return cropped


class Inference():
    def __init__(self, model_path, yolov5_path, device="cuda"):
        self.device = device
        self.G = FullGenerator(256, 512, 8, channel_multiplier=1, narrow=0.5, device=device).to(device)
        self.G.eval()
        self.G.load_state_dict(torch.load(model_path))
        self.yolonet = yolov5(yolov5_path, confThreshold=0.3, nmsThreshold=0.5, objThreshold=0.3)

    def inference(self, img_rgb):
        dets = self.yolonet.detect(img_rgb)
        dets = self.yolonet.postprocess(img_rgb, dets)
        [confidence, bbox, landmark] = dets[0]
        landmark = landmark.reshape([5, 2])
        aligned_img = crop_with_ldmk(img_rgb, landmark)
        with torch.no_grad():
            img_tensor = torch.tensor(aligned_img.copy(), dtype=torch.float32).to(self.device).permute(2, 0, 1)[None] / 127.5 - 1.0
            fake_img = self.G(img_tensor)
            res = (fake_img.clamp(-1, 1).permute(0, 2, 3, 1).cpu().numpy()[0] + 1.) * 127.5
        return res 


parser = argparse.ArgumentParser()
parser.add_argument("--img_path", type=str, default="")
parser.add_argument("--save_path", type=str, default="result.png")
parser.add_argument("--cartoon_model", type=str, default="./saved_models/style1.pth")
parser.add_argument("--yoloface_model", type=str, default="./saved_models/yolov5s-face.onnx")
parser.add_argument("--device", type=str, default="cuda")

args = parser.parse_args()
infer = Inference(model_path=args.cartoon_model, yolov5_path=args.yoloface_model, device=args.device)
img_bgr = cv2.imread(args.img_path)[..., :3]
img_rgb = img_bgr[..., ::-1]
res = infer.inference(img_rgb.copy())
cv2.imwrite(args.save_path, res[..., ::-1])
