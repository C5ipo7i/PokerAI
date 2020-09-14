import torch
import torch.nn as nn
import torch.nn.functional as F
from poker_env.datatypes import Globals,SUITS,RANKS
import numpy as np
from models.model_utils import strip_padding


class NetworkFunctions(object):
    def __init__(self,nA,nB):
        self.nA = nA
        self.nB = nB
        self.nC = nA - 2 + self.nB

    def wrap_action(self,action,betsize_category,previous_action):
        """
        Wraps split action/betsize into flat action.
        Bets and raises are combined into one.
        """
        actions = torch.zeros(self.nC)
        if action < 3:
            actions[action] = 1
        else: # Bet or raise
            actions[betsize_category + 3] = 1
        return torch.argmax(actions, dim=0).unsqueeze(0)

    def unwrap_action(self,action:torch.Tensor,previous_action:torch.Tensor):
        """Unwraps flat action into action_category and betsize_category"""
        # print(action,previous_action)
        actions = torch.zeros(self.nA)
        betsizes = torch.zeros(self.nB)
        # actions[action[action < 3]] = 1
        if action < 3:
            actions[action] = 1
        elif previous_action == 5 or previous_action == 0: # Unopened
            actions[3] = 1
            bet_category = action - 3
            betsizes[bet_category] = 1
        else: # facing bet or raise
            actions[4] = 1
            bet_category = action - 3
            betsizes[bet_category] = 1
        int_actions = torch.argmax(actions, dim=0).unsqueeze(-1)
        int_betsizes = torch.argmax(betsizes, dim=0).unsqueeze(-1)
        return int_actions,int_betsizes

    # def unwrap_action(self,action:torch.Tensor,previous_action:torch.Tensor):
    #     """Unwraps flat action into action_category and betsize_category"""
    #     # print(action,previous_action)
    #     actions_output = torch.zeros(action.size(0),self.nA)
    #     betsizes = torch.zeros(action.size(0),self.nB)
    #     # actions[action[action < 3]] = 1
    #     # for i,action in enumerate(actions):
    #     if action < 3:
    #         actions_output[:,action] = 1
    #     elif previous_action == 5 or previous_action == 0: # Unopened
    #         actions_output[:,3] = 1
    #         bet_category = action - 3
    #         betsizes[:,bet_category] = 1
    #     else: # facing bet or raise
    #         actions_output[:,4] = 1
    #         bet_category = action - 3
    #         betsizes[:,bet_category] = 1
    #     int_actions = torch.argmax(actions_output, dim=-1)
    #     int_betsizes = torch.argmax(betsizes, dim=-1)
    #     return int_actions,int_betsizes

################################################
#              Processing Layers               #
################################################

class ProcessHandBoard(nn.Module):
    def __init__(self,params,hand_length,hidden_dims=(15,32,32)):
        super().__init__()
        self.hand_length = hand_length
        self.one_hot_suits = torch.nn.functional.one_hot(torch.arange(0,5))
        self.one_hot_ranks = torch.nn.functional.one_hot(torch.arange(0,RANKS.HIGH))
        # Input is (b,4,2) -> (b,4,4) and (b,4,13)
        self.suit_conv = nn.Sequential(
            nn.Conv1d(5+hand_length, 64, kernel_size=1, stride=1),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
        )
        self.rank_conv = nn.Sequential(
            nn.Conv1d(5+hand_length, 64, kernel_size=5, stride=1),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
        )
        self.hidden_layers = nn.ModuleList()
        self.bn_layers = nn.ModuleList()
        for i in range(len(hidden_dims)-1):
            self.hidden_layers.append(nn.Linear(hidden_dims[i],hidden_dims[i+1]))
            self.bn_layers.append(nn.BatchNorm1d(64))
        self.maxlen = params['maxlen']
        # self.initialize(critic)

    def initialize(self,critic):
        if critic:
            self.forward = self.forward_critic
        else:
            self.forward = self.forward_actor

    def forward_critic(self,x):
        """x: concatenated hand and board. alternating rank and suit."""
        B,M,C = x.size()
        ranks = x[:,:,::2]
        suits = x[:,:,1::2]
        hero_ranks = ranks[:,:,:2]
        # villain_ranks = ranks[:,:,2:4]
        board_ranks = ranks[:,:,2:]
        hero_suits = suits[:,:,:2]
        # villain_suits = suits[:,:,2:4]
        board_suits = suits[:,:,4:]
        hero_hand_ranks = torch.cat((hero_ranks,board_ranks),dim=-1)
        hero_hand_suits = torch.cat((hero_suits,board_suits),dim=-1)
        # villain_hand_ranks = torch.cat((villain_ranks,board_ranks),dim=-1)
        # villain_hand_suits = torch.cat((villain_suits,board_suits),dim=-1)
        hero_hot_ranks = self.one_hot_ranks[hero_hand_ranks]
        hero_hot_suits = self.one_hot_suits[hero_hand_suits]
        # villain_hot_ranks = self.one_hot_ranks[villain_hand_ranks]
        # villain_hot_suits = self.one_hot_suits[villain_hand_suits]
        hero_activations = []
        # villain_activations = []
        for i in range(M):
            hero_s = self.suit_conv(hero_hot_suits[:,i,:,:].float())
            hero_r = self.rank_conv(hero_hot_ranks[:,i,:,:].float())
            hero_activations.append(torch.cat((hero_r,hero_s),dim=-1))
            villain_s = self.suit_conv(villain_hot_suits[:,i,:,:].float())
            villain_r = self.rank_conv(villain_hot_ranks[:,i,:,:].float())
            villain_activations.append(torch.cat((villain_r,villain_s),dim=-1))
        hero = torch.stack(hero_activations).view(B,M,-1)
        villain = torch.stack(villain_activations).view(B,M,-1)
        return hero - villain

    def forward(self,x):
        """x: concatenated hand and board. alternating rank and suit."""
        B,M,C = x.size()
        # print(B,M,C)
        ranks = x[:,:,::2]
        suits = x[:,:,1::2]
        # print(suits)
        # print(ranks.size(),suits.size())
        hot_ranks = self.one_hot_ranks[ranks]
        hot_suits = self.one_hot_suits[suits]
        activations = []
        for i in range(M):
            s = self.suit_conv(hot_suits[:,i,:,:].float())
            r = self.rank_conv(hot_ranks[:,i,:,:].float())
            activations.append(torch.cat((r,s),dim=-1))
        return torch.stack(activations).view(B,M,-1)

class ProcessOrdinal(nn.Module):
    def __init__(self,params):
        super().__init__()
        self.mapping = params['mapping']
        self.street_emb = nn.Embedding(embedding_dim=params['embedding_size'], num_embeddings=4)
        self.action_emb = nn.Embedding(embedding_dim=params['embedding_size'], num_embeddings=6)
        self.position_emb = nn.Embedding(embedding_dim=params['embedding_size'], num_embeddings=2)
        self.order_emb = nn.Embedding(embedding_dim=params['embedding_size'], num_embeddings=2)

    def forward(self,x):
        order = self.order_emb(torch.arange(2))
        street = self.street_emb(x[:,0].long())
        hero_position = self.position_emb(x[:,1].long()) + order[0]
        vil_position = self.position_emb(x[:,2].long()) + order[1]
        previous_action = self.action_emb(x[:,3].long())
        ordinal_output = torch.cat((street,hero_position,vil_position,previous_action),dim=-1)
        return ordinal_output

class ProcessContinuous(nn.Module):
    def __init__(self,params):
        super().__init__()
        self.mapping = params['mapping']
        self.betsize_fc = nn.Linear(1,params['embedding_size'])
        self.stack_fc = nn.Linear(1,params['embedding_size'])
        self.call_fc = nn.Linear(1,params['embedding_size'])
        self.odds_fc = nn.Linear(1,params['embedding_size'])
        self.order_emb = nn.Embedding(embedding_dim=params['embedding_size'], num_embeddings=5)
        
    def forward(self,x):
        M,C = x.size()
        # 
        previous_betsize = x[:,0].unsqueeze(-1)
        hero_stack = x[:,1].unsqueeze(-1)
        villain_stack = x[:,2].unsqueeze(-1)
        amnt_to_call = x[:,3].unsqueeze(-1)
        pot_odds = x[:,4].unsqueeze(-1)

        order = self.order_emb(torch.arange(5))
        bets = []
        heros = []
        villains = []
        calls = []
        odds = []
        for i in range(M):
            bets.append(self.betsize_fc(previous_betsize[i]) + order[0])
            heros.append(self.stack_fc(hero_stack[i]) + order[1])
            villains.append(self.stack_fc(villain_stack[i]) + order[2])
            calls.append(self.call_fc(amnt_to_call[i]) + order[3])
            odds.append(self.odds_fc(pot_odds[i]) + order[4])
        bet = torch.stack(bets)
        hero = torch.stack(heros)
        villain = torch.stack(villains)
        call = torch.stack(calls)
        odd = torch.stack(odds)
        continuous_output = torch.stack((bet,hero,villain,call,odd),dim=-1).view(M,-1)
        return continuous_output

class PreProcessPokerInputs(nn.Module):
    def __init__(self,params,critic=False):
        super().__init__()
        self.maxlen = params['maxlen']
        self.mapping = params['mapping']
        hand_length = Globals.HAND_LENGTH_DICT[params['game']]
        self.hand_board = ProcessHandBoard(params,hand_length)
        self.continuous = ProcessContinuous(params)
        self.ordinal = ProcessOrdinal(params)
        self.initialize(critic)

    def initialize(self,critic):
        if critic:
            self.forward = self.forward_critic
        else:
            self.forward = self.forward_actor

    def forward_critic(self,x):
        h = self.hand_board(x[:,:,self.mapping['observation']['hand_board']].long())
        # h.size(B,M,240)
        o = self.continuous(x[:,:,self.mapping['observation']['continuous'].long()])
        # o.size(B,M,5)
        c = self.ordinal(x[:,:,self.mapping['observation']['ordinal'].long()])
        # h.size(B,M,128)
        combined = torch.cat((h,o,c),dim=-1)
        return combined

    def forward_actor(self,x):
        stripped_x = strip_padding(x,self.maxlen).squeeze(0)
        M,C = stripped_x.size()
        h = self.hand_board(stripped_x[:,self.mapping['state']['hand_board']].long())
        # h.size(B,M,240)
        o = self.continuous(stripped_x[:,self.mapping['state']['continuous'].long()])
        # o.size(B,M,5)
        c = self.ordinal(stripped_x[:,self.mapping['state']['ordinal'].long()])
        # h.size(B,M,128)
        combined = torch.cat((h,o,c),dim=-1)
        return combined

    
class PreProcessLayer(nn.Module):
    def __init__(self,params):
        super().__init__()
        self.maxlen = params['maxlen']
        self.state_mapping = params['state_mapping']
        hand_length = Globals.HAND_LENGTH_DICT[params['game']]
        self.hand_board = ProcessHandBoard(params,hand_length)
        # self.continuous = ProcessContinuous(params)
        # self.ordinal = ProcessOrdinal(params)
        self.action_emb = nn.Embedding(embedding_dim=params['embedding_size'], num_embeddings=6)
        self.betsize_fc = nn.Linear(1,params['embedding_size'])

    def forward(self,x):
        B,M,C = x.size()
        h = self.hand_board(x[:,:,self.state_mapping['hand_board']].long())
        # h.size(B,M,240)
        last_a = x[:,:,self.state_mapping['last_action']].long()
        bets = []
        # for i in range()
        last_b = x[:,:,self.state_mapping['last_betsize']]
        # print(last_a.size(),last_b.size())
        emb_a = self.action_emb(last_a)
        embedded_bets = []
        for i in range(M):
            embedded_bets.append(self.betsize_fc(last_b[:,i]))
        embeds = torch.stack(embedded_bets)
        # print('embeds',embeds.size())
        # print('emb_a',emb_a.size())
        # o = self.continuous(x[:,:,self.mapping['observation']['continuous'].long()])
        # o.size(B,M,5)
        # c = self.ordinal(x[:,:,self.mapping['observation']['ordinal'].long()])
        # h.size(B,M,128)
        if embeds.dim() == 2:
            embeds = embeds.unsqueeze(0)
        combined = torch.cat((h,emb_a,embeds),dim=-1)
        # print(h.size(),emb_a.size(),embeds.size())
        # print(combined.size())
        return combined

class PreProcessHistory(nn.Module):
    def __init__(self,params,critic=False):
        super().__init__()
        self.mapping = params['mapping']
        self.hand_emb = Embedder(5,255)
        self.action_emb = Embedder(6,256)
        self.betsize_fc = nn.Linear(1,256)
        self.maxlen = 10
        self.initialize(critic)

    def initialize(self,critic):
        if critic:
            # self.one_hot_kuhn = torch.nn.functional.one_hot(torch.arange(0,4))
            # self.one_hot_actions = torch.nn.functional.one_hot(torch.arange(0,6))
            # self.conv = nn.Sequential(
            #     nn.Conv1d(2, 32, kernel_size=3, stride=1),
            #     nn.BatchNorm1d(32),
            #     nn.ReLU(inplace=True)
            # )
            self.forward = self.forward_critic
        else:
            self.forward = self.forward_actor

    def forward_critic(self,x):
        stripped_x = strip_padding(x,self.maxlen).squeeze(0)
        M,C = stripped_x.size()
        hand = stripped_x[:,self.mapping['state']['rank']].long()
        h = self.hand_emb(hand)
        last_action = stripped_x[:,self.mapping['state']['previous_action']].long()
        last_action_emb = self.action_emb(last_action)
        # o.size(B,M,5)
        last_betsize = stripped_x[:,self.mapping['state']['previous_betsize']].float()
        if last_betsize.dim() == 1:
            last_betsize = last_betsize.unsqueeze(1)
        # h.size(B,M,128)
        combined = torch.cat([h,last_action_emb,last_betsize],dim=-1)
        return combined

    def forward_actor(self,x):
        stripped_x = strip_padding(x,self.maxlen).squeeze(0)
        hand = stripped_x[:,self.mapping['state']['rank']].long()
        hand = self.hand_emb(hand)
        # h.size(B,M,240)
        last_action = stripped_x[:,self.mapping['state']['previous_action']].long()
        last_action_emb = self.action_emb(last_action)
        # o.size(B,M,5)
        previous_betsize = stripped_x[:,self.mapping['state']['previous_betsize']].float()
        if previous_betsize.dim() == 1:
            previous_betsize = previous_betsize.unsqueeze(1)
        # h.size(B,M,128)
        # b1 = self.betsize_fc(previous_betsize)
        combined = torch.cat([hand,last_action_emb,previous_betsize],dim=-1)
        return combined

################################################
#                Helper Layers                 #
################################################

class GaussianNoise(nn.Module):
    """Gaussian noise regularizer.

    Args:
        sigma (float, optional): relative standard deviation used to generate the
            noise. Relative means that it will be multiplied by the magnitude of
            the value your are adding the noise to. This means that sigma can be
            the same regardless of the scale of the vector.
        is_relative_detach (bool, optional): whether to detach the variable before
            computing the scale of the noise. If `False` then the scale of the noise
            won't be seen as a constant but something to optimize: this will bias the
            network to generate vectors with smaller values.
    """

    def __init__(self, sigma=0.1, is_relative_detach=True):
        super().__init__()
        self.sigma = sigma
        self.is_relative_detach = is_relative_detach
        self.noise = torch.tensor(0).float()#.to(device)

    def forward(self, x):
        if self.training and self.sigma != 0:
            scale = self.sigma * x.detach() if self.is_relative_detach else self.sigma * x
            sampled_noise = self.noise.repeat(*x.size()).normal_() * scale
            x = x + sampled_noise
        return x 

class Embedder(nn.Module):
    def __init__(self,vocab_size,d_model):
        super().__init__()
        self.embed = nn.Embedding(vocab_size,d_model)
    def forward(self,x):
        return self.embed(x)

class positionalEncoder(nn.Module):
    def __init__(self,d_model, max_seq_len = 80):
        super().__init__()
        self.d_model = d_model
        pe = torch.zeros(maxlen_seq,d_model)
        for pos in range(maxlen):
            for i in range(0,d_model,2):
                pe[pos,i] = pos / math.sin(10000 ** ((2*i)/d_model))
                pe[pos,i+1] = pos / math.cos(10000 ** ((2*(i+1))/d_model))
        pe.unsqueeze(0)
        self.register_buffer('pe',pe)
        
    def forward(self,x):
        x = x * math.sqrt(self.d_model)
        seq_len = x.size(1)
        x = x + Variable(pe[:,:seq_len],requires_grad=False).cuda()
        return x

class SelfAttentionWide(nn.Module):
    def __init__(self, emb, heads=8, mask=False):
        """
        :param emb:
        :param heads:
        :param mask:
        """

        super().__init__()

        self.emb = emb
        self.heads = heads
        self.mask = mask

        self.tokeys = nn.Linear(emb, emb * heads, bias=False)
        self.toqueries = nn.Linear(emb, emb * heads, bias=False)
        self.tovalues = nn.Linear(emb, emb * heads, bias=False)

        self.unifyheads = nn.Linear(heads * emb, emb)

    def forward(self, x):

        b, t, e = x.size()
        h = self.heads
        assert e == self.emb, f'Input embedding dim ({e}) should match layer embedding dim ({self.emb})'

        keys    = self.tokeys(x)   .view(b, t, h, e)
        queries = self.toqueries(x).view(b, t, h, e)
        values  = self.tovalues(x) .view(b, t, h, e)

        # compute scaled dot-product self-attention

        # - fold heads into the batch dimension
        keys = keys.transpose(1, 2).contiguous().view(b * h, t, e)
        queries = queries.transpose(1, 2).contiguous().view(b * h, t, e)
        values = values.transpose(1, 2).contiguous().view(b * h, t, e)

        queries = queries / (e ** (1/4))
        keys    = keys / (e ** (1/4))
        # - Instead of dividing the dot products by sqrt(e), we scale the keys and values.
        #   This should be more memory efficient

        # - get dot product of queries and keys, and scale
        dot = torch.bmm(queries, keys.transpose(1, 2))

        assert dot.size() == (b*h, t, t)

        if self.mask: # mask out the upper half of the dot matrix, excluding the diagonal
            mask_(dot, maskval=float('-inf'), mask_diagonal=False)

        dot = F.softmax(dot, dim=2)
        # - dot now has row-wise self-attention probabilities

        # apply the self attention to the values
        out = torch.bmm(dot, values).view(b, h, t, e)

        # swap h, t back, unify heads
        out = out.transpose(1, 2).contiguous().view(b, t, h * e)

        return self.unifyheads(out)

class SelfAttentionNarrow(nn.Module):

    def __init__(self, emb, heads=8, mask=False):
        """
        :param emb:
        :param heads:
        :param mask:
        """

        super().__init__()

        assert emb % heads == 0, f'Embedding dimension ({emb}) should be divisible by nr. of heads ({heads})'

        self.emb = emb
        self.heads = heads
        self.mask = mask

        s = emb // heads
        # - We will break the embedding into `heads` chunks and feed each to a different attention head

        self.tokeys    = nn.Linear(s, s, bias=False)
        self.toqueries = nn.Linear(s, s, bias=False)
        self.tovalues  = nn.Linear(s, s, bias=False)

        self.unifyheads = nn.Linear(heads * s, emb)

    def forward(self, x):

        b, t, e = x.size()
        h = self.heads
        assert e == self.emb, f'Input embedding dim ({e}) should match layer embedding dim ({self.emb})'

        s = e // h
        x = x.view(b, t, h, s)

        keys    = self.tokeys(x)
        queries = self.toqueries(x)
        values  = self.tovalues(x)

        assert keys.size() == (b, t, h, s)
        assert queries.size() == (b, t, h, s)
        assert values.size() == (b, t, h, s)

        # Compute scaled dot-product self-attention

        # - fold heads into the batch dimension
        keys = keys.transpose(1, 2).contiguous().view(b * h, t, s)
        queries = queries.transpose(1, 2).contiguous().view(b * h, t, s)
        values = values.transpose(1, 2).contiguous().view(b * h, t, s)

        queries = queries / (e ** (1/4))
        keys    = keys / (e ** (1/4))
        # - Instead of dividing the dot products by sqrt(e), we scale the keys and values.
        #   This should be more memory efficient

        # - get dot product of queries and keys, and scale
        dot = torch.bmm(queries, keys.transpose(1, 2))

        assert dot.size() == (b*h, t, t)

        if self.mask: # mask out the upper half of the dot matrix, excluding the diagonal
            mask_(dot, maskval=float('-inf'), mask_diagonal=False)

        dot = F.softmax(dot, dim=2)
        # - dot now has row-wise self-attention probabilities

        # apply the self attention to the values
        out = torch.bmm(dot, values).view(b, h, t, s)

        # swap h, t back, unify heads
        out = out.transpose(1, 2).contiguous().view(b, t, s * h)

        return self.unifyheads(out)

class TransformerBlock(nn.Module):

    def __init__(self, emb, heads, mask, seq_length, ff_hidden_mult=4, dropout=0.0, wide=True):
        super().__init__()

        self.attention = SelfAttentionWide(emb, heads=heads, mask=mask) if wide \
                    else SelfAttentionNarrow(emb, heads=heads, mask=mask)
        self.mask = mask

        self.norm1 = nn.LayerNorm(emb)
        self.norm2 = nn.LayerNorm(emb)

        self.ff = nn.Sequential(
            nn.Linear(emb, ff_hidden_mult * emb),
            nn.ReLU(),
            nn.Linear(ff_hidden_mult * emb, emb)
        )

        self.do = nn.Dropout(dropout)

    def forward(self, x):

        attended = self.attention(x)

        x = self.norm1(attended + x)

        x = self.do(x)

        fedforward = self.ff(x)

        x = self.norm2(fedforward + x)

        x = self.do(x)

        return x

class CTransformer(nn.Module):
    """
    Transformer for classifying sequences
    """
    def __init__(self, emb, heads, depth, seq_length, num_classes, max_pool=True, dropout=0.0, wide=False):
        """
        :param emb: Embedding dimension
        :param heads: nr. of attention heads
        :param depth: Number of transformer blocks
        :param seq_length: Expected maximum sequence length
        :param num_tokens: Number of tokens (usually words) in the vocabulary
        :param num_classes: Number of classes.
        :param max_pool: If true, use global max pooling in the last layer. If false, use global
                         average pooling.
        """
        super().__init__()

        self.max_pool = max_pool

        # self.token_embedding = nn.Embedding(embedding_dim=emb, num_embeddings=num_tokens)
        # self.pos_embedding = nn.Embedding(embedding_dim=emb, num_embeddings=seq_length)

        tblocks = []
        for i in range(depth):
            tblocks.append(
                TransformerBlock(emb=emb, heads=heads, seq_length=seq_length, mask=False, dropout=dropout, wide=wide))

        self.tblocks = nn.Sequential(*tblocks)

        self.toprobs = nn.Linear(emb, num_classes)

        self.do = nn.Dropout(dropout)

    def forward(self, x):
        """
        :param x: A batch by sequence length integer tensor of token indices.
        :return: predicted log-probability vectors for each token based on the preceding tokens.
        """
        # tokens = self.token_embedding(x)
        # b, t, e = tokens.size()

        # positions = self.pos_embedding(torch.arange(t, device=d()))[None, :, :].expand(b, t, e)
        # x = tokens + positions
        x = self.do(x)

        x = self.tblocks(x)

        x = x.max(dim=1)[0] if self.max_pool else x.mean(dim=1) # pool over the time dimension

        x = self.toprobs(x)

        return x #F.log_softmax(x, dim=1)