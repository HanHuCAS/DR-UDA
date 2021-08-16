
import sys
# from __future__ import division

import os
import random
from PIL import Image
import torch
import numpy as np
import torch.backends.cudnn as cudnn
from torch.autograd import Variable
from torch.nn import init
import scipy.io as scio
import math
from torch.nn import DataParallel

from pdb import set_trace as st
# custom weights initialization called on netG and netD
def weights_init(m):
    classname = m.__class__.__name__
    if classname.find('Conv') != -1:
        m.weight.data.normal_(0.0, 0.02)
    elif classname.find('BatchNorm') != -1:
        m.weight.data.normal_(1.0, 0.02)
        m.bias.data.fill_(0)

# compute the current classification accuracy
def compute_acc(preds, labels):
    correct = 0
    preds_ = preds.data.max(1)[1]
    correct = preds_.eq(labels.data).cpu().sum()
    acc = float(correct) / float(len(labels.data)) * 100.0
    return acc


class Logger(object):
    def __init__(self):
        self.terminal = sys.stdout  #stdout
        self.file = None

    def open(self, file, mode=None):
        if mode is None: mode ='w'
        self.file = open(file, mode)

    def write(self, message, is_terminal=1, is_file=1 ):
        if '\r' in message: is_file=0

        if is_terminal == 1:
            self.terminal.write(message)
            self.terminal.flush()
            #time.sleep(1)

        if is_file == 1:
            self.file.write(message)
            self.file.flush()

    def flush(self):
        # this flush method is needed for python 3 compatibility.
        # this handles the flush command by doing nothing.
        # you might want to specify some extra behavior here.
        pass



def make_variable(tensor, volatile=False):
    if torch.cuda.is_available():
        tensor = tensor.cuda()
    return tensor


def tensor2im(image_tensor, imtype=np.uint8):
    image_numpy = image_tensor.cpu().detach().numpy()
    if image_numpy.shape[0] == 1:
        image_numpy = np.tile(image_numpy, (3, 1, 1))
    # image_numpy = (np.transpose(image_numpy, (1, 2, 0)) + 1) / 2.0 * 255.0
    image_numpy = np.transpose(image_numpy, (1, 2, 0)) * 255.0
    return image_numpy.astype(imtype)


def denormalize(x, std, mean):
    """Invert normalization, and then convert array into image."""
    out = x * std + mean
    return out.clamp(0, 1)


def weights_init_xavier(m):
    classname = m.__class__.__name__
    # print(classname)
    if classname.find('Conv') != -1:
        init.xavier_normal_(m.weight.data, gain=1)
    elif classname.find('Linear') != -1:
        init.xavier_normal_(m.weight.data, gain=1)
        init.constant_(m.bias.data, 0.0)
    elif classname.find('BatchNorm2d') != -1:
        # init.uniform(m.weight.data, 1.0, 0.02)
        init.uniform(m.weight.data, 0.02, 1.0)
        init.constant_(m.bias.data, 0.0)


def weights_init_normal(m):
    classname = m.__class__.__name__
    # print(classname)
    if classname.find('Conv') != -1:
        init.uniform(m.weight.data, 0.0, 0.02)
    elif classname.find('Linear') != -1:
        init.uniform(m.weight.data, 0.0, 0.02)
        init.constant_(m.bias.data, 0.0)
    elif classname.find('BatchNorm2d') != -1:
        # init.uniform(m.weight.data, 1.0, 0.02)
        init.uniform(m.weight.data, 0.02, 1.0)
        init.constant_(m.bias.data, 0.0)


def weights_init_kaiming(m):
    classname = m.__class__.__name__
    # print(classname)
    if classname.find('Conv') != -1:
        init.kaiming_normal(m.weight.data, a=0, mode='fan_in')
    elif classname.find('Linear') != -1:
        init.kaiming_normal(m.weight.data, a=0, mode='fan_in')
        init.constant_(m.bias.data, 0.0)
    elif classname.find('BatchNorm2d') != -1:
        # init.uniform(m.weight.data, 1.0, 0.02)
        init.uniform(m.weight.data, 0.02, 1.0)
        init.constant_(m.bias.data, 0.0)


def weights_init_orthogonal(m):
    classname = m.__class__.__name__
    # print(classname)
    if classname.find('Conv') != -1:
        init.orthogonal_(m.weight.data, gain=1)
    elif classname.find('Linear') != -1:
        init.orthogonal_(m.weight.data, gain=1)
        init.constant_(m.bias.data, 0.0)
    elif classname.find('BatchNorm2d') != -1:
        # init.uniform(m.weight.data, 1.0, 0.02)
        init.uniform(m.weight.data, 0.02, 1.0)
        init.constant_(m.bias.data, 0.0)


def weights_init_orthogonal_rnn(m):
    classname = m.__class__.__name__
    if classname.find('LSTM') != -1:
        init.orthogonal_(m.all_weights[0][0], gain=1)
        init.orthogonal_(m.all_weights[0][1], gain=1)
        init.constant_(m.all_weights[0][2], 1)
        init.constant_(m.all_weights[0][3], 1)
    elif classname.find('Linear') != -1:
        init.xavier_normal_(m.weight.data, gain=1)
        init.constant_(m.bias.data, 0.0)


def init_weights(net, init_type='normal'):
    print('initialization method [%s]' % init_type)
    if init_type == 'normal':
        net.apply(weights_init_normal)
    elif init_type == 'xavier':
        net.apply(weights_init_xavier)
    elif init_type == 'kaiming':
        net.apply(weights_init_kaiming)
    elif init_type == 'orthogonal':
        net.apply(weights_init_orthogonal)
    elif init_type == 'orthogonal_rnn':
        net.apply(weights_init_orthogonal_rnn)
    else:
        raise NotImplementedError('initialization method [%s] is not implemented' % init_type)


def init_random_seed(manual_seed):
    """Init random seed."""
    seed = None
    if manual_seed is None:
        seed = random.randint(1, 10000)
    else:
        seed = manual_seed
    print("use random seed: {}".format(seed))
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    return seed


# def get_data_loader(name, data_root, batch_size, getreal):
#     """Get data loader by name."""
#     if name == "D3MAD":
#         return get_D3MAD(data_root, batch_size,getreal)


def init_model(net, restore, init_type, init=True):
    """Init models with cuda and weights."""
    # init weights of model
    if init:
        init_weights(net, init_type)

    # restore model weights
    if restore is not None and os.path.exists(restore):

        # original saved file with DataParallel
        state_dict = torch.load(restore)
        # create new OrderedDict that does not contain `module.`
        from collections import OrderedDict
        new_state_dict = OrderedDict()
        for k, v in state_dict.items():
            name = k[7:]  # remove `module.`
            new_state_dict[name] = v
        # load params
        net.load_state_dict(new_state_dict)

        # net.load_state_dict(torch.load(restore))
        net.restored = True
        print("*************Restore model from: {}".format(os.path.abspath(restore)))

    if torch.cuda.is_available():
        cudnn.benchmark = True
        net.cuda()

    return net


# def save_model(net, filename):
#     """Save trained model."""
#     if not os.path.exists(args.model_root):
#         os.makedirs(args.model_root)
#     torch.save(net.state_dict(),
#                os.path.join(args.model_root, filename))
#     print("save pretrained model to: {}".format(os.path.join(args.model_root,
#                                                              filename)))

# def save_trainedmodel(net, filename):
#     """Save trained model."""
#     if not os.path.exists(os.path.join(args.model_root, args.namesave)):
#         os.makedirs(os.path.join(args.model_root, args.namesave))
#     torch.save(net.state_dict(),
#                os.path.join(args.model_root, args.namesave, filename))
#     print("save pretrained model to: {}".format(os.path.join(args.model_root, args.namesave,
#                                                              filename)))


def mkdir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def mkdirs(paths):
    if isinstance(paths, list) and not isinstance(paths, str):
        for path in paths:
            mkdir(path)
    else:
        mkdir(paths)



def save_image(image_numpy, image_path):
    image_pil = Image.fromarray(image_numpy)
    image_pil = image_pil.resize((128, 128), resample=Image.BICUBIC)
    image_pil.save(image_path)


def get_inf_iterator(data_loader):
    """Inf data iterator."""
    while True:
        for catimages, labels in data_loader:
            yield (catimages, labels)


def get_inf_iterator_tst(data_loader):
    """Inf data iterator."""
    while True:
        for catimages, labels in data_loader:
            yield (catimages, labels)



