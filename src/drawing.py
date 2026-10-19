"""在图片上按识别顺序绘制编号框。"""
import random

import cv2


def plot_one_box(x, img, color=None, label=None, line_thickness=None):
    """在 img 上绘制一个 [x1, y1, x2, y2] 框，可附带标签。"""
    tl = line_thickness or round(0.002 * (img.shape[0] + img.shape[1]) / 2) + 1  # line/font thickness
    color = color or [random.randint(0, 255) for _ in range(3)]
    c1, c2 = (int(x[0]), int(x[1])), (int(x[2]), int(x[3]))
    cv2.rectangle(img, c1, c2, color, thickness=tl, lineType=cv2.LINE_AA)
    if label:
        tf = max(tl - 1, 1)  # font thickness
        t_size = cv2.getTextSize(label, 0, fontScale=tl / 3, thickness=tf)[0]
        c2 = c1[0] + t_size[0], c1[1] - t_size[1] - 3
        cv2.rectangle(img, c1, c2, color, -1, cv2.LINE_AA)  # filled
        cv2.putText(img, label, (c1[0], c1[1] - 2), 0, tl / 3, [225, 255, 255], thickness=tf, lineType=cv2.LINE_AA)
    return img


def draw_boxes(img, result):
    """按顺序给每个框标注 1、2、3…，每个框随机一种颜色。"""
    colors = [[random.randint(0, 255) for _ in range(3)] for _ in range(len(result))]
    for i, xyxy in enumerate(result):
        img = plot_one_box(xyxy, img, label=str(i + 1), color=colors[i], line_thickness=1)
    return img


def drow_img(image_path, result, save_image_path="res2.jpg"):
    img = cv2.imread(image_path)
    cv2.imwrite(save_image_path, draw_boxes(img, result))
