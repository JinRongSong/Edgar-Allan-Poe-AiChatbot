# -*- coding: utf-8 -*-
"""aichatbot.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1VT0cFDNoylag8ZDWQLCZkdjLUyIGehN-

Loading the dataset to train
"""

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.nn import functional


data = pd.read_csv("https://raw.githubusercontent.com/ducklord2407/Edgar-Allan-Poe-AiChatbot/main/preprocessed_data.csv")

device = 'cuda' if torch.cuda.is_available() else 'cpu'
poems = data[["text"]]

poems = poems.transpose()
poems["merged"] = poems.agg('\n'.join, axis = 1)
text = poems["merged"].values[0]

character = list(set(text))
character.sort()
size = len(character)

device = 'cuda' if torch.cuda.is_available() else 'cpu'

learning_rate = 1e-3
batch = 32 
block = 128
trainingIters = 3000
eval_interval = 100
eval_iters = 200
embed = 192
heads = 6
layers = 6

cToNum = {}
numToC = {}
for i, char in enumerate(character):
  cToNum[char] = i
  numToC[i] = char

def encode(s):
  final = []
  for char in s:
    final += [cToNum[char]]
  return final
    
def decode(nums):
  final = []
  for num in nums:
    final += [numToC[num]]
  return "".join(final)

data = torch.tensor(encode(text), dtype=torch.long)

print(data.shape, data.dtype)

n = int(0.9*len(data))
train_data = data[:n]
val_data = data[n:]

import random

def get_batch(train):
    if train:
      data = train_data
    else:
      data = val_data

    startingPoint = []
    for i in range(batch):
      startingPoint += [random.randint(0,len(data)-block-1)]
    
    x = torch.stack([data[start:start + block] for start in startingPoint])
    y = torch.stack([data[start+1:start+ block +1] for start in startingPoint])

    x = x.to(device)
    y = y.to(device)
    return x, y

class AttentionHead(nn.Module):
  def __init__(self, size):
    super(AttentionHead, self).__init__()
    self.k = nn.Linear(embed, size, bias=False)
    self.q = nn.Linear(embed, size, bias=False)
    self.val = nn.Linear(embed, size, bias=False)
    self.register_buffer('attention', torch.tril(torch.ones(block, block)))

  def forward(self, input):
    x,y,z = input.shape
    k = self.k(input)
    q = self.q(input)
    k = k.transpose(-2,-1)
    weights = q @ k * (z**-0.5)

    lowertri = torch.tril(torch.ones(y, y))

    weights = weights.masked_fill(lowertri == 0, float('-inf'))
    wei = functional.softmax(weights, dim = -1)

    v = self.val(input)
    out = wei @ v
    return out

class MultiAttention(nn.Module):
  def __init__(self, heads, headSize):
    super(MultiAttention, self).__init__()
    self.heads = nn.ModuleList([AttentionHead(headSize) for i in range(heads)])
  
  def forward(self, input):
    output = []
    for head in self.heads:
      output += [head.forward(input)]
    return output

class feedForward(nn.Module):
  def __init__(self, embed):
    super(feedForward, self).__init__()
    self.first = nn.Linear(embed, 4*embed)
    self.second = nn.ReLU()
    self.third = nn.Linear(4*embed, embed)
  
  def forward(self, input):
    one = self.first(input)
    two = self.second(one)
    final = self.third(two)
    return final

class Block(nn.Module):
  def __init__(self, embed, heads):
    super(Block, self).__init__()
    size = embed // heads
    self.attention = MultiAttention(heads, size)
    self.feed = feedForward(embed)
    self.lnorm1 = nn.LayerNorm(embed)
    self.lnorm2 = nn.LayerNorm(embed)
  
  def forward(self, input):
    normal = self.lnorm1(input)
    output = self.attention.forward(normal)
    normal = self.lnorm2(normal)
    final = self.feed.forward(normal)
    return final

from collections import OrderedDict
class Bigram(nn.Module):
    def __init__(self):
      super(Bigram, self).__init__()
      self.tokenTable = nn.Embedding(size, embed)
      self.positionTable = nn.Embedding(block, embed)
      blockOrder = OrderedDict()
      for i in range(layers):
        blockOrder[str(i)] = Block(embed, heads)
      self.blocks = nn.Sequential(blockOrder)

      self.finalNorm = nn.LayerNorm(embed)
      self.finalLinear = nn.Linear(embed, size)
          
    def forward(self, index, targets = None):
      token = self.tokenTable(index)
      position = self.positionTable(torch.arange(index.shape[1], device=device))
      pred = self.blocks(token+position)
      pred = self.finalNorm(pred)
      pred = self.finalLinear(pred)

      if targets is None:
          loss = None
      else:
          x, y, z = pred.shape
          pred = pred.view(x*y, z)
          targets = targets.view(x*y)
          loss = functional.cross_entropy(pred, targets)
      return pred, loss

    
    def generate(self, idx, max_generate):
      for i in range(max_generate):
        pred, loss = self.forward(idx[:, -block:])
        probs = functional.softmax(pred[:, -1, :], dim=-1)
        idx_next = torch.multinomial(probs, num_samples=1)
        idx = torch.cat((idx, idx_next), dim=1)
      return idx

model = Bigram()
m = model.to(device)
# pred, loss = model(batchX, batchY)
# print(pred.shape)
# print(loss)
# print(decode(model.generate(idx = torch.zeros((1, 1), dtype=torch.long), max_new_tokens=100)[0].tolist()))

optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)

for iter in range(trainingIters):
    # sample a batch of data
    sampleX, sampleY = get_batch(True)

    # evaluate the loss
    pred, loss = model(sampleX, sampleY)
    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    optimizer.step()

# generate from the model
context = torch.zeros((1, 1), dtype=torch.long, device=device)

print(decode(model.generate(context, max_generate=2000)[0].tolist()))