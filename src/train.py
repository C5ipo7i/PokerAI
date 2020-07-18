import os
import poker.datatypes as pdt
import models.network_config as ng
import copy
import torch
import sys
import numpy as np
from pymongo import MongoClient
from collections import defaultdict
import copy

from db import MongoDB
from poker.env import Poker
from agents.agent import ParallelAgent,FullAgent

def pad_state(state,maxlen):
    N = maxlen - state.shape[1]
    padding = np.zeros(N)
    return padded_state

def generate_trajectories(env,actor,training_params):
    """We want to store """
    trajectories = defaultdict(lambda:[])
    for e in range(training_params['epochs']):
        trajectory = defaultdict(lambda:{'states':[],'obs':[],'betsize_masks':[],'action_masks':[], 'actions':[],'action_category':[],'action_probs':[],'action_prob':[],'betsize':[],'rewards':[]})
        state,obs,done,action_mask,betsize_mask = env.reset()
        cur_player = env.current_player
        trajectory[cur_player]['states'].append(copy.copy(state))
        trajectory[cur_player]['action_masks'].append(copy.copy(action_mask))
        trajectory[cur_player]['betsize_masks'].append(copy.copy(betsize_mask))
        while not done:
            actor_outputs = actor(state,action_mask,betsize_mask)
            trajectory[cur_player]['actions'].append(actor_outputs['action'])
            trajectory[cur_player]['action_category'].append(actor_outputs['action_category'])
            trajectory[cur_player]['action_prob'].append(actor_outputs['action_prob'])
            trajectory[cur_player]['action_probs'].append(actor_outputs['action_probs'])
            trajectory[cur_player]['betsize'].append(actor_outputs['betsize'])
            state,obs,done,action_mask,betsize_mask = env.step(actor_outputs)
            cur_player = env.current_player
            if not done:
                trajectory[cur_player]['states'].append(state)
                trajectory[cur_player]['action_masks'].append(action_mask)
                trajectory[cur_player]['betsize_masks'].append(betsize_mask)
        assert len(trajectory[cur_player]['betsize']) == len(trajectory[cur_player]['betsize_masks'])
        rewards = env.player_rewards()
        for position in trajectory.keys():
            N = len(trajectory[position]['betsize_masks'])
            trajectory[position]['rewards'] = [rewards[position]] * N
            trajectories[position].append(trajectory[position])
    print(trajectories.keys())
    insert_data(trajectories,env.state_mapping,env.obs_mapping,training_params['training_round'],training_params['game'],training_params['id'],training_params['epochs'])

def insert_data(training_data:dict,mapping:dict,obs_mapping,training_round:int,gametype:str,id:int,epochs:int):
    """
    takes trajectories and inserts them into db for data analysis and learning.
    """
    client = MongoClient('localhost', 27017,maxPoolSize=10000)
    db = client['poker']
    keys = training_data.keys()
    positions = [position for position in keys if position in ['SB','BB']]   
    for position in positions:
        for i,poker_round in enumerate(training_data[position]):
            states = poker_round['states']
            observations = poker_round['obs']
            actions = poker_round['actions']
            action_prob = poker_round['action_prob']
            action_probs = poker_round['action_probs']
            action_categories = poker_round['action_category']
            betsize_masks = poker_round['betsize_masks']
            action_masks = poker_round['action_masks']
            rewards = poker_round['rewards']
            betsizes = poker_round['betsize']
            assert(isinstance(rewards,list))
            assert(isinstance(actions,list))
            assert(isinstance(action_prob,list))
            assert(isinstance(action_probs,list))
            assert(isinstance(observations,list))
            assert(isinstance(states,list))
            for step,state in enumerate(states):
                state_json = {
                    'training_round':training_round,
                    'poker_round':i + (id * epochs),
                    'state':state.tolist(),
                    'action_probs':action_probs[step].tolist(),
                    'action_prob':action_prob[step].tolist(),
                    'action':actions[step],
                    'action_category':action_categories[step],
                    'betsize_mask':betsize_masks[step].tolist(),
                    'action_mask':action_masks[step].tolist(),
                    'betsize':betsizes[step],
                    'reward':rewards[step]
                }
                db['game_data'].insert_one(state_json)
    client.close()

def return_value_mask(actions):
    print('actions',actions)
    M = 1#actions.shape[0]
    value_mask = torch.zeros(M,5)
    value_mask[torch.arange(M),actions] = 1
    value_mask = value_mask.bool()
    return value_mask

def scale_rewards(self,rewards,factor=1):
    """Scales rewards between -1 and 1, with optional factor to increase valuation differences"""
    return (2 * ((rewards + self.min_reward) / (self.max_reward + self.min_reward)) - 1) * factor

def learning_update(actor,critic,params):
    critic_optimizer = params['critic_optimizer']
    actor_optimizer = params['actor_optimizer']
    mongo = MongoDB()
    query = {'training_round':0}
    projection = {'state':1,'betsize_mask':1,'action_mask':1,'action':1,'reward':1,'_id':0}
    data = mongo.get_data(query,projection)
    for poker_round in data:
        state = poker_round['state']
        action = poker_round['action']
        reward = poker_round['reward']
        betsize_mask = poker_round['betsize_mask']
        action_mask = poker_round['action_mask']
        ## Critic update ##
        local_values = critic(state)['value']
        print('local_values',local_values)
        value_mask = return_value_mask(action)
        print('value_mask',value_mask)
        TD_error = local_values[value_mask] - reward
        critic_loss = (TD_error**2*0.5).mean()
        # critic_loss = F.smooth_l1_loss(scaled_rewards.view(value_mask.size(0)),TD_error,reduction='sum')
        critic_optimizer.zero_grad()
        critic_loss.backward()
        torch.nn.utils.clip_grad_norm_(critic.parameters(), params['gradient_clip'])
        critic_optimizer.step()
        # Agent.soft_update(local_critic,target_critic,tau)

        ## Actor update ##
        # expected_value = (actor_inputs['action_probs'].view(-1) * target_values.view(-1)).view(value_mask.size()).detach().sum(-1)
        # advantages = (target_values[value_mask] - expected_value).view(-1)
        # policy_loss = (-actor_inputs['action_prob'].view(-1) * advantages).sum()
        # self.actor_optimizer.zero_grad()
        # policy_loss.backward()
        # torch.nn.utils.clip_grad_norm_(self.local_actor.parameters(), self.gradient_clip)
        # self.actor_optimizer.step()
        # Agent.soft_update(self.local_actor,self.target_actor,self.tau)

        # outputs = actor(np.array(state),np.array(action_mask),np.array(betsize_mask))
        # print(outputs)

def train(env,agent,training_params):
    for e in range(training_params['epochs']):
        sys.stdout.write('\r')
        state,obs,done,mask,betsize_mask = env.reset()
        while not done:
            actor_outputs = agent(state,mask,betsize_mask)
            state,obs,done,mask,betsize_mask = env.step(actor_outputs)
        ml_inputs = env.ml_inputs()
        agent.learn(ml_inputs)
        for position in ml_inputs.keys():
            training_data[position].append(ml_inputs[position])
        training_data['action_records'].append(env.action_records)
        sys.stdout.write("[%-60s] %d%%" % ('='*(60*(e+1)//training_params['epochs']), (100*(e+1)//training_params['epochs'])))
        sys.stdout.flush()
        sys.stdout.write(", epoch %d"% (e+1))
        sys.stdout.flush()
    agent.save_weights(os.path.join(training_params['save_dir'],training_params['agent_name']))
    return training_data