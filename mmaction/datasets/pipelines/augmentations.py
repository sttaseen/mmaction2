import random

import mmcv
import numpy as np

from ..registry import PIPELINES


@PIPELINES.register_module
class MultiScaleCrop(object):
    """Crop an image with a randomly selected scale.

    Randomly select the w and h scales from a list of scales. Scale of 1 means
    the base size, which is the minimal of image weight and height. The scale
    level of w and h is controlled to be smaller than a certain value to
    prevent too large or small aspect ratio.
    Required keys are "imgs", added or modified keys are "imgs", "crop_bbox",
    "img_shape" and "scales".

    Attributes:
        input_size (int | tuple[int]): (w, h) of network input.
        scales (list[float]): Weight and height scales to be selected.
        max_wh_scale_gap (int): Maximum gap of w and h scale levels.
            Default: 1.
        random_crop (bool): If set to True, the cropping bbox will be randomly
            sampled, otherwise it will be sampler from 5 fixed regions:
            "upper left", "upper right", "lower left", "lower right", "center"
            Default: False.
    """

    def __init__(self,
                 input_size,
                 scales=(1, ),
                 max_wh_scale_gap=1,
                 random_crop=False):
        assert isinstance(scales, tuple)
        self.input_size = input_size if not isinstance(input_size, int) \
            else (input_size, input_size)
        self.scales = scales
        self.max_wh_scale_gap = max_wh_scale_gap
        self.random_crop = random_crop

    def __call__(self, results):
        imgs = results['imgs']
        img_h, img_w = imgs.shape[-2:]

        base_size = min(img_h, img_w)

        crop_sizes = [int(base_size * s) for s in self.scales]

        candidate_sizes = []
        for i, h in enumerate(crop_sizes):
            for j, w in enumerate(crop_sizes):
                if abs(i - j) <= self.max_wh_scale_gap:
                    candidate_sizes.append([w, h])

        crop_size = random.choice(candidate_sizes)
        for i in range(2):
            if abs(crop_size[i] - self.input_size[i]) < 3:
                crop_size[i] = self.input_size[i]

        crop_w, crop_h = crop_size

        if self.random_crop:
            x_offset = random.randint(0, img_w - crop_w)
            y_offset = random.randint(0, img_h - crop_h)
        else:
            w_step = (img_w - crop_w) // 4
            h_step = (img_h - crop_h) // 4
            candidate_offsets = []
            candidate_offsets.append((0, 0))  # upper left
            candidate_offsets.append((4 * w_step, 0))  # upper right
            candidate_offsets.append((0, 4 * h_step))  # lower left
            candidate_offsets.append((4 * w_step, 4 * h_step))  # lower right
            candidate_offsets.append((2 * w_step, 2 * h_step))  # center

            x_offset, y_offset = random.choice(candidate_offsets)

        results['crop_bbox'] = np.array(
            [x_offset, y_offset, x_offset + crop_w, y_offset + crop_h],
            dtype=np.int32)
        results['imgs'] = imgs[:, :, y_offset:y_offset + crop_h,
                               x_offset:x_offset + crop_w]

        results['img_shape'] = results['imgs'].shape[-3:]
        results['scales'] = self.scales
        return results

    def __repr__(self):
        repr_str = self.__class__.__name__
        repr_str += ('(input_size={}, scales={}, max_wh_scale_gap={}, '
                     'random_crop={})').format(self.input_size, self.scales,
                                               self.max_wh_scale_gap,
                                               self.random_crop)
        return repr_str


@PIPELINES.register_module
class Resize(object):
    """Resize images to a specific size.

    Required keys are "imgs", added or modified keys are "imgs", "img_shape",
    "keep_ratio", "scale_factor" and "resize_size".

    Attributes:
        scale (int | Tuple[int]): Target spatial size (h, w).
        keep_ratio (bool): If set to True, Images will be resized without
            changing the aspect ratio. Otherwise, it will resize images to a
            given size.
        interpolation (str): Algorithm used for interpolation:
            "nearest" | "bilinear". Default: "bilinear".
    """

    def __init__(self, scale, keep_ratio=True, interpolation='bilinear'):
        if isinstance(scale, (float, int)):
            if scale <= 0:
                raise ValueError(
                    'Invalid scale {}, must be positive.'.format(scale))
        self.scale = scale
        self.keep_ratio = keep_ratio
        self.interpolation = interpolation

    def __call__(self, results):
        imgs = results['imgs'].transpose([0, 2, 3, 1])
        if self.keep_ratio:
            tuple_list = [
                mmcv.imrescale(img, self.scale, return_scale=True)
                for img in imgs
            ]
            imgs, scale_factors = list(zip(*tuple_list))
            self.scale_factor = scale_factors[0]
        else:
            tuple_list = [
                mmcv.imresize(img, self.scale, return_scale=True)
                for img in imgs
            ]
            imgs, w_scales, h_scales = list(zip(*tuple_list))
            self.scale_factor = np.array(
                [w_scales[0], h_scales[0], w_scales[0], h_scales[0]],
                dtype=np.float32)

        imgs = np.array(imgs).transpose([0, 3, 1, 2])
        results['imgs'] = imgs
        results['img_shape'] = results['imgs'].shape[-3:]
        results['keep_ratio'] = self.keep_ratio
        results['scale_fatcor'] = self.scale_factor

        return results

    def __repr__(self):
        repr_str = self.__class__.__name__
        repr_str += '(scale={}, keep_ratio={}, interpolation={})'. \
            format(self.scale, self.keep_ratio, self.interpolation)
        return repr_str


@PIPELINES.register_module
class Flip(object):
    """Flip the input images with a probability.

    Reverse the order of elements in the given imgs with a specific direction.
    The shape of the imgs is preserved, but the elements are reordered.
    Required keys are "imgs", added or modified keys are "imgs"
    and "flip_direction".

    Attributes:
         direction (str): Flip imgs horizontally or vertically. Options are
            "horiziontal" | "vertival". Default: "horizontal".
    """

    def __init__(self, flip_ratio=0.5, direction='horizontal'):
        assert direction in ['horizontal', 'vertical']
        self.flip_ratio = flip_ratio
        self.direction = direction

    def __call__(self, results):
        if np.random.rand() < self.flip_ratio:
            flip = True
        else:
            flip = False

        if flip:
            if self.direction == 'horizontal':
                results['imgs'] = np.flip(results['imgs'], axis=3).copy()
            else:
                results['imgs'] = np.flip(results['imgs'], axis=2).copy()

        results['flip'] = flip
        results['flip_direction'] = self.direction

        return results

    def __repr__(self):
        repr_str = self.__class__.__name__
        repr_str += '(flip_ratio={}, direction={})'.format(
            self.flip_ratio, self.direction)
        return repr_str


@PIPELINES.register_module
class Normalize(object):
    """Normalize images with the given mean and std value.

    Required keys are "imgs", added or modified keys are "imgs"
    and "img_norm_cfg".

    Attributes:
        mean (np.ndarray): Mean values of different channels.
        std (np.ndarray): Std values of different channels.
        to_rgb (bool): Whether to convert channels from BGR to RGB.
    """

    def __init__(self, mean, std, to_rgb=True):
        self.mean = np.array(mean, dtype=np.float32)
        self.std = np.array(std, dtype=np.float32)
        self.to_rgb = to_rgb

    def __call__(self, results):
        imgs = results['imgs'].astype(np.float32)

        if self.to_rgb:
            imgs = imgs[:, ::-1, ...].copy()

        imgs -= self.mean[:, None, None]
        imgs /= self.std[:, None, None]

        results['imgs'] = imgs
        results['img_norm_cfg'] = dict(
            mean=self.mean, std=self.std, to_rgb=self.to_rgb)

        return results

    def __repr__(self):
        repr_str = self.__class__.__name__
        repr_str += '(mean={}, std={}, to_rgb={})'.format(
            self.mean, self.std, self.to_rgb)
        return repr_str


@PIPELINES.register_module
class CenterCrop(object):
    """Crop the center area from images.

    Required keys are "imgs", added or modified keys are "imgs", "crop_bbox"
    and "img_shape".

    Attributes:
        crop_size(tuple[int]): (w, h) of crop size.
    """

    def __init__(self, crop_size=224):
        if isinstance(crop_size, int):
            self.crop_size = (crop_size, crop_size)
        else:
            self.crop_size = crop_size
        assert mmcv.is_tuple_of(crop_size, int)

    def __call__(self, results):
        imgs = results['imgs']

        img_h, img_w = imgs.shape[-2:]
        crop_w, crop_h = self.crop_size

        left = (img_w - crop_w) // 2
        top = (img_h - crop_h) // 2
        right = left + crop_w
        bottom = top + crop_h
        results['crop_bbox'] = np.array([left, top, right, bottom])
        results['imgs'] = imgs[:, :, top:bottom, left:right]
        results['img_shape'] = results['imgs'].shape[-3:]
        return results

    def __repr__(self):
        repr_str = self.__class__.__name__
        repr_str += '(crop_size={})'.format(self.crop_size)
        return repr_str


@PIPELINES.register_module
class ThreeCrop(object):
    """Crop images into three crops.

    Crop the images equally into three crops with equal intervals along the
    shorter side.
    Required keys are "imgs", added or modified keys are "imgs", "crop_box" and
    "img_shape".

    Attributes:
        crop_size(tuple[int]): (w, h) of crop size.
    """

    def __init__(self, crop_size):
        if isinstance(crop_size, int):
            self.crop_size = (crop_size, crop_size)
        else:
            self.crop_size = crop_size
        assert mmcv.is_tuple_of(crop_size, int)

    def __call__(self, results):
        imgs = results['imgs']
        img_h, img_w = imgs.shape[-2:]
        crop_w, crop_h = self.crop_size
        assert crop_h == img_h or crop_w == img_w

        if crop_h == img_h:
            w_step = (img_w - crop_w) // 2
            offsets = [
                (0, 0),  # left
                (2 * w_step, 0),  # right
                (w_step, 0),  # middle
            ]
        elif crop_w == img_w:
            h_step = (img_h - crop_h) // 2
            offsets = [
                (0, 0),  # top
                (0, 2 * h_step),  # down
                (0, h_step),  # middle
            ]

        img_crops = []
        crop_bboxes = []
        for x_offset, y_offset in offsets:
            bbox = [x_offset, y_offset, x_offset + crop_w, y_offset + crop_h]
            crop = imgs[:, :, y_offset:y_offset + crop_h,
                        x_offset:x_offset + crop_w]
            img_crops.append(crop)
            crop_bboxes.extend([bbox for _ in range(imgs.shape[0])])

        crop_bboxes = np.array(crop_bboxes)
        imgs = np.concatenate(img_crops, axis=0)
        results['imgs'] = imgs
        results['crop_bbox'] = crop_bboxes
        results['img_shape'] = results['imgs'].shape[-3:]

        return results

    def __repr__(self):
        repr_str = self.__class__.__name__
        repr_str += '(crop_size={})'.format(self.crop_size)
        return repr_str


@PIPELINES.register_module
class TenCrop(object):
    """Crop the images into 10 crops (corner + center + flip).

    Crop the four corners and the center part of the image with the same
    given crop_size, and flip it horizontally.
    Required keys are "imgs", added or modified keys are "imgs", "crop_bbox"
    and "img_shape".

    Attributes:
        crop_size(tuple[int]): (w, h) of crop size.
    """

    def __init__(self, crop_size=224):
        if isinstance(crop_size, int):
            self.crop_size = (crop_size, crop_size)
        else:
            self.crop_size = crop_size
        assert mmcv.is_tuple_of(crop_size, int)

    def __call__(self, results):
        imgs = results['imgs']

        img_h, img_w = imgs.shape[-2:]
        crop_w, crop_h = self.crop_size

        w_step = (img_w - crop_w) // 4
        h_step = (img_h - crop_h) // 4

        offsets = [
            (0, 0),  # upper left
            (4 * w_step, 0),  # upper right
            (0, 4 * h_step),  # lower left
            (4 * w_step, 4 * h_step),  # lower right
            (2 * w_step, 2 * h_step),  # center
        ]

        img_crops = list()
        crop_bboxes = list()
        for x_offset, y_offsets in offsets:
            crop = imgs[:, :, y_offsets:y_offsets + crop_h,
                        x_offset:x_offset + crop_w]
            flip_crop = np.flip(crop, axis=3).copy()
            bbox = [x_offset, y_offsets, x_offset + crop_w, y_offsets + crop_h]
            img_crops.append(crop)
            img_crops.append(flip_crop)
            crop_bboxes.extend([bbox for _ in range(imgs.shape[0])])

        crop_bboxes = np.array(crop_bboxes)
        imgs = np.concatenate(img_crops, axis=0)
        results['imgs'] = imgs
        results['crop_box'] = crop_bboxes
        results['img_shape'] = results['imgs'].shape[-3:]

        return results

    def __repr__(self):
        repr_str = self.__class__.__name__
        repr_str += '(crop_size={})'.format(self.crop_size)
        return repr_str
