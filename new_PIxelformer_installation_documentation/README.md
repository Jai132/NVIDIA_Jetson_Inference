# How to setup Pixelformer?
Install Miniconda or Anaconda (if you are using a jetson device install [Miniconda](https://docs.anaconda.com/miniconda/miniconda-install/) or [Archiconda](https://github.com/Archiconda), preferably **miniconda**)



Now, head over to your terminal:
```
conda create -n pixelformer python=3.8
conda activate pixelformer

```

Then install cuda toolkit in the environment from [here](https://anaconda.org/nvidia/cuda):


>[!NOTE]
>if you are using a jetson device or any other device with a GPU, dont mess up the device by installing the cuda toolkit locally, install it in your environment via conda.


Once the toolkit has been installed, we will now install PyTorch, check [here](https://pytorch.org/get-started/previous-versions/) for version compatibility with CUDA

```
#for jetson devices running jetpack 5.1.3, we install cuda toolkit 11.8 in the environment

conda install nvidia/label/cuda-11.8.0::cuda

#then we install the corresponding PyTorch library

conda install pytorch==2.0.0 torchvision==0.15.0 torchaudio==2.0.0 pytorch-cuda=11.8 -c pytorch -c nvidia
```
Now install some more dependencies:
```
pip install opencv-python
pip install matplotlib tqdm tensorboardX timm depthai
```
