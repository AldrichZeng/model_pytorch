import torch
import torch.nn as nn
import torch.utils.data as Data
import torchvision
from torch.autograd import Variable
import numpy as np
from datetime import datetime
import vgg
from train import create_net
import pretrainedmodels
import os
import random
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA           #加载PCA算法包






# 超参数
EPOCH = 10
LR = 0.0001



class AutoEncoder(nn.Module):
    def __init__(self):
        super(AutoEncoder, self).__init__()
        self.input_dimension=3*3*512
        self.encoder = nn.Sequential(
            #todo:之前激活函数是tanh，是否有必要改？
            #todo:自编码器的层数是否太多
            nn.Linear(self.input_dimension, 2304),
            nn.ReLU(True),
            nn.Dropout(),
            nn.Linear(2304, 576),
            # nn.ReLU(True),
            # nn.Dropout(),
            # nn.Linear(576, 144),
            # nn.ReLU(True),
            # nn.Dropout(),
            # nn.Linear(144, 18),
        )

        self.decoder = nn.Sequential(
            # nn.Linear(18, 144),
            # nn.ReLU(True),
            # nn.Dropout(),
            # nn.Linear(144, 576),
            # nn.ReLU(True),
            # nn.Dropout(),
            nn.Linear(576, 2304),
            nn.ReLU(True),
            nn.Dropout(),
            nn.Linear(2304,self.input_dimension),
            nn.Sigmoid(),
        )

    def forward(self, x):
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return encoded, decoded

def pca(conv_weight):
    pca = PCA(n_components=27)  # int(image_dim_reduced.shape[1]*0.5))  # 加载PCA算法，设置降维后主成分数目为32
    # pca = PCA(n_components='mle')

    encoded=pca.fit_transform(conv_weight)
    return encoded

    # s=10
    # file_list=os.listdir(dir)
    # validation_file_list=random.sample(file_list,int(len(file_list)/s))
    # train_file_list=list(set(file_list).difference(set(validation_file_list)))
    # for file in train_file_list:
    #     x=np.load(dir+file)                 #[out_channels,in_channels,kernel_size,kernel_size]
    #     x=np.reshape(x,(x.shape[0],-1))     #each row is one kernel

def train(dir='/home/victorfang//PycharmProjects/model_pytorch/data/model_params/weight/'):
    # cross_validation,use 1/s of the data as validation set
    s=10
    file_list=os.listdir(dir)
    validation_file_list=random.sample(file_list,int(len(file_list)/s))
    train_file_list=list(set(file_list).difference(set(validation_file_list)))
    for file in train_file_list:
        x=np.load(dir+file)                 #[out_channels,in_channels,kernel_size,kernel_size]
        x=np.reshape(x,(x.shape[0],-1))     #each row is one kernel
        print(x.shape)
        encoded=pca(x)
        print()

    print()




    # use auto_encoder to encode weight. seemed not work.
    # auto_encoder = AutoEncoder()
    # optimizer = torch.optim.Adam(auto_encoder.parameters(), lr=LR)
    # loss_func = nn.MSELoss()
    # #loss_func=nn.L1Loss()
    # for epoch in range(10):
    #     auto_encoder.train()
    #     i=1
    #     for file in train_file_list:
    #         x=np.load(dir+file)                 #[out_channels,in_channels,kernel_size,kernel_size]
    #         x=np.reshape(x,(x.shape[0],-1))     #each row is one kernel
    #         x=np.pad(x,((0,0),(0,auto_encoder.input_dimension-x.shape[1])),'constant')    #pad kernel with 0 at the end
    #         x=torch.from_numpy(x)
    #         encoded, decoded = auto_encoder(x)
    #         loss = loss_func(decoded, x)#+(torch.sum(torch.abs(decoded-torch.mean(x))))
    #         optimizer.zero_grad()
    #         loss.backward()
    #         optimizer.step()
    #         print("{} step:{},file_name:{}  loss is:{}".format(datetime.now(),i,file,loss))
    #         i=i+1
    #
    #     #plt.figure(figsize=[14, 20], clear=True, num=epoch)
    #     plt.figure(10)
    #     auto_encoder.eval()
    #     for file in validation_file_list:
    #         x = np.load(dir + file)  # [out_channels,in_channels,kernel_size,kernel_size]
    #         x = np.reshape(x, (x.shape[0], -1))  # each row is one kernel
    #         x = np.pad(x, ((0, 0), (0, auto_encoder.input_dimension - x.shape[1])),
    #                    'constant')  # pad kernel with 0 at the end
    #         x = torch.from_numpy(x)
    #         encoded, decoded = auto_encoder(x)
    #         plt.subplot(1,2,1)
    #         plt.plot(decoded[0].data.numpy()[0:1000],'.')
    #         plt.subplot(1,2,2)
    #         plt.plot(x[0].data.numpy()[0:1000],'.')
    #         plt.show()



          

model_urls = [

    'vgg11',
    'vgg13',
    'vgg16',
    'vgg19',
    'vgg11_bn',
    'vgg13_bn',
    'vgg16_bn',
    'vgg19_bn'
]

root='/home/victorfang/PycharmProjects/model_pytorch/data/model_params/'

def download_weight():
    for net_name in model_urls:
        net=create_net(net_name,pretrained=True)
        for i in range(len(net.features)):
            mod=net.features[i]
            if isinstance(mod, torch.nn.modules.conv.Conv2d):
                weight=mod.weight.data.cpu().numpy()
                np.save(root+'weight/'+net_name+','+str(i),weight)
                bias=mod.bias.data.cpu().numpy()
                np.save(root+'bias/'+net_name+','+str(i),bias)

if __name__ == "__main__":


    train()
    # net_name='alexnet'
    # net=pretrainedmodels.__dict__[net_name](num_classes=1000, pretrained='imagenet')
    # for i in range(len(net._features)):
    #     mod = net._features[i]
    #     if isinstance(mod, torch.nn.modules.conv.Conv2d):
    #         weight = mod.weight.data.cpu().numpy()
    #         np.save(root + 'weight/' + net_name + ',' + str(i), weight)
    #         bias = mod.bias.data.cpu().numpy()
    #         np.save(root + 'bias/' + net_name + ',' + str(i), bias)
    #download_weight()
