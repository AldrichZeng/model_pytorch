import torch
import numpy as np
import vgg
import copy
import torch.nn as nn
def replace_layers(module,old_mod,new_mod):
    for i in range(len(old_mod)):
        if module is old_mod[i]:
            return new_mod[i]
    return module

def prune_conv_layer_resnet(net, layer_index, filter_index, modules_list):
    """
    :param net:
    :param layer_index: 要删的卷基层的索引,从1开始
    :param filter_index: 要删layer_index层中的哪个filter
    :return:
    """
    conv_to_prune = None  # 获取要删filter的那层conv
    batch_norm = None  # 如果有的话：获取要删的conv后的batch normalization层
    next_conv = None  # 如果有的话：获取要删的那层后一层的conv，用于删除对应通道
    i = 0

    module_to_prune = ""
    next_module = ""
    bn_module = ""
    for string in modules_list:
        if module_to_prune != "":
            if "conv" in string:
                next_module += string
                break
            elif "bn" in string:
                bn_module += string
            else:
                continue
        if "conv" in string:
            i += 1
            if i == layer_index:
                module_to_prune += string

    i = 0
    for mod in net.modules():
        if conv_to_prune is not None:
            if isinstance(mod, torch.nn.modules.conv.Conv2d):  # 要删的filter后一层的conv
                next_conv = mod
                break
            elif isinstance(mod, torch.nn.modules.BatchNorm2d):  # 要删的filter后一层的batch normalization
                batch_norm = mod
            else:
                continue
        if isinstance(mod, torch.nn.modules.conv.Conv2d):
            i += 1
            if i == layer_index:  # 找到要删filter的conv
                conv_to_prune = mod

    new_conv = torch.nn.Conv2d(  # 创建新的conv替代要删filter的conv
        in_channels=conv_to_prune.in_channels,
        out_channels=conv_to_prune.out_channels - len(filter_index),
        kernel_size=conv_to_prune.kernel_size,
        stride=conv_to_prune.stride,
        padding=conv_to_prune.padding,
        dilation=conv_to_prune.dilation,
        groups=conv_to_prune.groups,
        bias=(conv_to_prune.bias is not None))

    # 复制其他filter
    old_weights = conv_to_prune.weight.data.cpu().numpy()
    new_weights = new_conv.weight.data.cpu().numpy()
    new_weights[:] = old_weights[
        [i for i in range(old_weights.shape[0]) if i not in filter_index]]  # 复制剩余的filters的weight

    if conv_to_prune.bias is not None:
        old_bias = conv_to_prune.bias.data.cpu().numpy()
        new_bias = new_conv.bias.data.cpu().numpy()
        new_bias[:] = old_bias[[i for i in range(old_bias.shape[0]) if i not in filter_index]]  # 复制剩余的filters的bias
    if torch.cuda.is_available():
        new_conv.cuda()

    # 替换
    tmp_list = module_to_prune.split(".")
    if (len(tmp_list) == 1):
        replace_module = getattr(net, '_modules')
        replace_module[module_to_prune] = new_conv
    else:
        tmp = getattr(net, '_modules')[tmp_list[0]]
        tmp=getattr(tmp,"_modules")[tmp_list[1]]
        tmp=getattr(tmp,"_modules")
        tmp[tmp_list[2]]=new_conv


    if batch_norm is not None:
        new_batch_norm = torch.nn.BatchNorm2d(new_conv.out_channels)
        new_batch_norm.num_batches_tracked = batch_norm.num_batches_tracked

        old_weights = batch_norm.weight.data.cpu().numpy()  # 删除weight
        new_weights = new_batch_norm.weight.data.cpu().numpy()
        new_weights[:] = old_weights[[i for i in range(old_weights.shape[0]) if i not in filter_index]]

        old_bias = batch_norm.bias.data.cpu().numpy()  # 删除bias
        new_bias = new_batch_norm.bias.data.cpu().numpy()
        new_bias[:] = old_bias[[i for i in range(old_bias.shape[0]) if i not in filter_index]]

        old_running_mean = batch_norm.running_mean.cpu().numpy()
        new_running_mean = new_batch_norm.running_mean.cpu().numpy()
        new_running_mean[:] = old_running_mean[[i for i in range(old_running_mean.shape[0]) if i not in filter_index]]

        old_running_var = batch_norm.running_var.cpu().numpy()
        new_running_var = new_batch_norm.running_var.cpu().numpy()
        new_running_var[:] = old_running_var[[i for i in range(old_running_var.shape[0]) if i not in filter_index]]

        if torch.cuda.is_available():
            new_batch_norm.cuda()
        # 替换
        tmp_list = bn_module.split(".")
        if (len(tmp_list) == 1):
            replace_module = getattr(net, '_modules')
            replace_module[bn_module] = new_batch_norm
        else:
            tmp = getattr(net, '_modules')[tmp_list[0]]
            tmp = getattr(tmp, "_modules")[tmp_list[1]]
            tmp = getattr(tmp, "_modules")
            tmp[tmp_list[2]] = new_batch_norm

    if next_conv is not None:  # next_conv中需要把对应的通道也删了
        next_new_conv = \
            torch.nn.Conv2d(in_channels=next_conv.in_channels - len(filter_index),
                            out_channels=next_conv.out_channels,
                            kernel_size=next_conv.kernel_size,
                            stride=next_conv.stride,
                            padding=next_conv.padding,
                            dilation=next_conv.dilation,
                            groups=next_conv.groups,
                            bias=(next_conv.bias is not None))

        old_weights = next_conv.weight.data.cpu().numpy()
        new_weights = next_new_conv.weight.data.cpu().numpy()
        new_weights[:] = old_weights[:, [i for i in range(old_weights.shape[1]) if i not in filter_index], :,
                         :]  # 复制剩余的filters的weight

        if next_conv.bias is not None:
            next_new_conv.bias.data = next_conv.bias.data
        if torch.cuda.is_available():
            next_new_conv.cuda()
        # 替换
        tmp_list = next_module.split(".")
        if (len(tmp_list) == 1):
            replace_module = getattr(net, '_modules')
            replace_module[next_module] = next_new_conv
        else:
            tmp = getattr(net, '_modules')[tmp_list[0]]
            tmp = getattr(tmp, "_modules")[tmp_list[1]]
            tmp = getattr(tmp, "_modules")
            tmp[tmp_list[2]] = next_new_conv

    else:
        # Prunning the last conv layer. This affects the first linear layer of the classifier.
        layer_index = 0
        old_linear_layer = None
        for _, module in net.classifier._modules.items():
            if isinstance(module, torch.nn.Linear):
                old_linear_layer = module
                break
            layer_index = layer_index + 1

        if old_linear_layer is None:
            raise BaseException("No linear layer found in classifier")
        params_per_input_channel = int(old_linear_layer.in_features / conv_to_prune.out_channels)

        new_linear_layer = \
            torch.nn.Linear(old_linear_layer.in_features - len(filter_index) * params_per_input_channel,
                            old_linear_layer.out_features)

        old_weights = old_linear_layer.weight.data.cpu().numpy()
        new_weights = new_linear_layer.weight.data.cpu().numpy()

        # node_index=filter_index
        node_index = []
        for f in filter_index:
            node_index.extend([i for i in range(f * params_per_input_channel, (f + 1) * params_per_input_channel)])

        new_weights[:] = old_weights[:,
                         [i for i in range(old_weights.shape[1]) if i not in node_index]]  # 复制剩余的filters的weight

        #
        # new_weights[:, : filter_index * params_per_input_channel] = \
        #     old_weights[:, : filter_index * params_per_input_channel]
        # new_weights[:, filter_index * params_per_input_channel:] = \
        #     old_weights[:, (filter_index + 1) * params_per_input_channel:]

        new_linear_layer.bias.data = old_linear_layer.bias.data

        if torch.cuda.is_available():
            new_linear_layer.cuda()

        net.classifier = torch.nn.Sequential(
            *(replace_layers(mod, [old_linear_layer], [new_linear_layer]) for mod in net.classifier))

    return net


def string_to_module(net, string):
    """
    将字符串表示的module转换成module类型
    """
    tmp_list = string.split(".")
    if (len(tmp_list) == 1):
        replace_module = getattr(net, string)
    else:
        tmp = getattr(net, tmp_list[0])
        tmp = getattr(tmp, tmp_list[1])
        replace_module = getattr(tmp, tmp_list[2])
    return replace_module



def prune_conv_layer(model, layer_index, filter_index):
    ''' layer_index:要删的卷基层的索引
        filter_index:要删layer_index层中的哪个filter
    '''
    conv=None                                                               #获取要删filter的那层conv
    batch_norm=None                                                         #如果有的话：获取要删的conv后的batch normalization层
    next_conv=None                                                          #如果有的话：获取要删的那层后一层的conv，用于删除对应通道
    i=0

    #todo:用引用可以直接改，可行
    # model.layer1.block0=torch.nn.Sequential(nn.Linear(512 * 7 * 7, 4096),
    #         nn.ReLU(True),
    #         nn.Dropout(),)

    for mod in model.modules():
        if conv is not None:
            if isinstance(mod, torch.nn.modules.conv.Conv2d):            #要删的filter后一层的conv
                next_conv = mod
                break
            elif isinstance(mod,torch.nn.modules.BatchNorm2d):             #要删的filter后一层的batch normalization
                batch_norm=mod
            else:
                continue
        if isinstance(mod,torch.nn.modules.conv.Conv2d):
            i+=1
            if i==layer_index:                                              #要删filter的conv
                conv=mod


    new_conv = torch.nn.Conv2d(                                             #创建新的conv替代要删filter的conv
                                in_channels=conv.in_channels,
                                out_channels=conv.out_channels - len(filter_index),
                                kernel_size=conv.kernel_size,
                                stride=conv.stride,
                                padding=conv.padding,
                                dilation=conv.dilation,
                                groups=conv.groups,
                                bias=(conv.bias is not None))

    #复制其他filter
    old_weights = conv.weight.data.cpu().numpy()
    new_weights=new_conv.weight.data.cpu().numpy()
    new_weights[:]=old_weights[[i for i in range(old_weights.shape[0]) if i not in filter_index]]  #复制剩余的filters的weight

    if conv.bias is not None:
        old_bias = conv.bias.data.cpu().numpy()
        new_bias = new_conv.bias.data.cpu().numpy()
        new_bias[:] = old_bias[[i for i in range(old_bias.shape[0]) if i not in filter_index]]  # 复制剩余的filters的bias
    if torch.cuda.is_available():
        new_conv.cuda()

    # tmp=getattr(model,'_modules')['features']
    # tmp=getattr(tmp,'_modules')
    # tmp['0']=new_conv
    #
    # model.features._modules['0']=new_conv

    model.features = torch.nn.Sequential(                                           #生成替换为new_conv的features
        *(replace_layers(mod, [conv], [new_conv]) for mod in model.features))

    if batch_norm is not None:
        new_batch_norm=torch.nn.BatchNorm2d(new_conv.out_channels)
        new_batch_norm.num_batches_tracked=batch_norm.num_batches_tracked

        old_weights = batch_norm.weight.data.cpu().numpy()                                      #删除weight
        new_weights = new_batch_norm.weight.data.cpu().numpy()
        new_weights[:] = old_weights[[i for i in range(old_weights.shape[0]) if i not in filter_index]]

        old_bias=batch_norm.bias.data.cpu().numpy()                                             #删除bias
        new_bias=new_batch_norm.bias.data.cpu().numpy()
        new_bias[:] = old_bias[[i for i in range(old_bias.shape[0]) if i not in filter_index]]

        old_running_mean=batch_norm.running_mean.cpu().numpy()
        new_running_mean=new_batch_norm.running_mean.cpu().numpy()
        new_running_mean[:] = old_running_mean[[i for i in range(old_running_mean.shape[0]) if i not in filter_index]]

        old_running_var=batch_norm.running_var.cpu().numpy()
        new_running_var=new_batch_norm.running_var.cpu().numpy()
        new_running_var[:] = old_running_var[[i for i in range(old_running_var.shape[0]) if i not in filter_index]]

        if torch.cuda.is_available():
            new_batch_norm.cuda()
        model.features = torch.nn.Sequential(
            *(replace_layers(mod, [batch_norm], [new_batch_norm]) for mod in model.features))
        

    if next_conv is not None:                                                       #next_conv中需要把对应的通道也删了
        next_new_conv = \
            torch.nn.Conv2d(in_channels=next_conv.in_channels - len(filter_index),
                            out_channels=next_conv.out_channels,
                            kernel_size=next_conv.kernel_size,
                            stride=next_conv.stride,
                            padding=next_conv.padding,
                            dilation=next_conv.dilation,
                            groups=next_conv.groups,
                            bias=(next_conv.bias is not None))

        old_weights = next_conv.weight.data.cpu().numpy()
        new_weights = next_new_conv.weight.data.cpu().numpy()
        new_weights[:] = old_weights[:,[i for i in range(old_weights.shape[1]) if i not in filter_index],:,:]  # 复制剩余的filters的weight

        if next_conv.bias is not None:
            next_new_conv.bias.data = next_conv.bias.data
        if torch.cuda.is_available():
            next_new_conv.cuda()
        model.features=torch.nn.Sequential(                                               #生成替换为new_next_conv的features
            *(replace_layers(mod,[next_conv],[next_new_conv]) for mod in model.features))

    else:
        # Prunning the last conv layer. This affects the first linear layer of the classifier.
        layer_index = 0
        old_linear_layer = None
        for _, module in model.classifier._modules.items():
            if isinstance(module, torch.nn.Linear):
                old_linear_layer = module
                break
            layer_index = layer_index + 1

        if old_linear_layer is None:
            raise BaseException("No linear layer found in classifier")
        params_per_input_channel = int(old_linear_layer.in_features / conv.out_channels)

        new_linear_layer = \
            torch.nn.Linear(old_linear_layer.in_features - len(filter_index)*params_per_input_channel,
                            old_linear_layer.out_features)

        old_weights = old_linear_layer.weight.data.cpu().numpy()
        new_weights = new_linear_layer.weight.data.cpu().numpy()

        # node_index=filter_index
        node_index=[]
        for f in filter_index:
            node_index.extend([i for i in range(f*params_per_input_channel,(f+1)*params_per_input_channel)])

        new_weights[:] = old_weights[:,[i for i in range(old_weights.shape[1]) if i not in node_index]]  # 复制剩余的filters的weight

        #
        # new_weights[:, : filter_index * params_per_input_channel] = \
        #     old_weights[:, : filter_index * params_per_input_channel]
        # new_weights[:, filter_index * params_per_input_channel:] = \
        #     old_weights[:, (filter_index + 1) * params_per_input_channel:]

        new_linear_layer.bias.data = old_linear_layer.bias.data

        if torch.cuda.is_available():
            new_linear_layer.cuda()

        model.classifier = torch.nn.Sequential(
            *(replace_layers(mod, [old_linear_layer], [new_linear_layer]) for mod in model.classifier))

    return model

def select_and_prune_filter(model,ord,layer_index=0,num_to_prune=0,percent_of_pruning=0):
    '''

    :param model: net model
    :param ord: which norm to compute as the standard. Support l1 and l2 norm
    :param layer_index: layer in which the filters being pruned. If being set to 0, all conv layers will be pruned.
    :param num_to_prune: number of filters to prune. Disabled if percent_of_pruning is not 0
    :param percent percent_of_pruning: percent of filters to prune for one conv
    :return: filter indexes in the [layer_index] layer
    '''
    if ord!=1 and ord !=2:
        raise TypeError('unsupported type of norm')

    i = 0
    conv_index=-1                                                       #index of the conv in model.features
    for mod in model.features:
        conv_index+=1
        if isinstance(mod, torch.nn.modules.conv.Conv2d):
            i += 1
            if i == layer_index:                                        # hit the conv to be pruned
                conv=mod
                break
    if percent_of_pruning is not 0:
        if num_to_prune is not 0:
            print('Warning: Param: num_to_prune disabled!')
        num_to_prune=int(conv.out_channels*percent_of_pruning)
    weights = model.features[conv_index].weight.data.cpu().numpy()  # get weight of all filters

    filter_norm=np.linalg.norm(weights,ord=ord,axis=(2,3))          #compute filters' norm
    if ord==1:
        filter_norm=np.sum(filter_norm,axis=1)
    elif ord==2:
        filter_norm=np.square(filter_norm)
        filter_norm=np.sum(filter_norm,axis=1)
    filter_min_norm_index=np.argsort(filter_norm)
    model=prune_conv_layer(model,layer_index,filter_min_norm_index[:num_to_prune])

    return model



if __name__ == "__main__":
    model= vgg.vgg16_bn(pretrained=True)
    select_and_prune_filter(model,layer_index=3,num_to_prune=2,ord=2)
    # prune_conv_layer(model,layer_index=3,filter_index=1)