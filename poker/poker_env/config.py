import os
import numpy as np

class Config(object):
    def __init__(self):
        self.act_dict = {'SB':0,'BB':1}
        self.agent = 'actor_critic'
        self.maxlen = 10
        self.training_params = {
                'epochs':2500,
                'training_round':0,
                'save_dir':os.path.join(os.getcwd(),'checkpoints')
            }
        self.agent_params = {
            'BUFFER_SIZE':10000,
            'MIN_BUFFER_SIZE':200,
            'BATCH_SIZE':50,
            'ALPHA':0.6, # 0.7 or 0.6,
            'START_BETA':0.5, # from 0.5-1,
            'END_BETA':1,
            'LEARNING_RATE':0.00025,
            'EPSILON':1,
            'MIN_EPSILON':0.01,
            'GAMMA':0.99,
            'TAU':0.01,
            'UPDATE_EVERY':4,
            'CLIP_NORM':10,
            'L2': 0.01,
            'embedding':True,
            'network':None,
            'critic_network':None,
            'actor_network':None,
            'critic_type':'q',
            'embedding_size': 32,
            'actor_lr':1e-3,
            'critic_lr':4e-7,
            'frozen_layer_path' : os.path.join(os.getcwd(),'checkpoints/PartialHandRegression'),
            'frozen_layer' : False,
            'actor_path':os.path.join(os.getcwd(),'checkpoints/RL_actor'),
        }
        self.global_mapping = {
            'board':np.array([0,1,2,3,4,5,6,7,8,9]),
            'board_ranks':np.array([0,2,4,6,8]),
            'board_suits':np.array([1,3,5,7,9]),
            'street':np.array([10]),
            'last_aggressive_position':np.array([11]),
            'last_aggressive_action':np.array([12]),
            'last_aggressive_betsize':np.array([13]),
            'last_position':np.array([14]),
            'last_action':np.array([15]),
            'last_betsize':np.array([16]),
            'blind':np.array([17]),
            'pot':np.array([18]),
            'amount_to_call':np.array([19]),
            'pot_odds':np.array([20]),
            'p1_position':np.array([21]),
            'p1_stacksize':np.array([22]),
            'p1_street_total':np.array([23]),
            'p1_status':np.array([24]),
            'p2_position':np.array([25]),
            'p2_stacksize':np.array([26]),
            'p2_street_total':np.array([27]),
            'p2_status':np.array([28]),
            'p3_position':np.array([29]),
            'p3_stacksize':np.array([30]),
            'p3_street_total':np.array([31]),
            'p3_status':np.array([32]),
        }
        self.state_mapping = {
            'hero_position':0,
            'hero_stacksize':1,
            'hero_hand':[2,3,4,5,6,7,8,9],
            'hero_ranks':[2,4,6,8],
            'hero_suits':[3,5,7,9],
            'board':[10,11,12,13,14,15,16,17,18,19],
            'board_ranks':[10,12,14,16,18],
            'board_suits':[11,13,15,17,19],
            'street':20,
            'last_aggressive_position':21,
            'last_aggressive_action':22,
            'last_aggressive_betsize':23,
            'last_position':24,
            'last_action':25,
            'last_betsize':26,
            'blind':27,
            'pot':28,
            'amount_to_call':29,
            'pot_odds':30,
            'player1_position':31,
            'player1_stacksize':32,
            'player1_street_total':33,
            'player1_status':34,
            'player2_position':35,
            'player2_stacksize':36,
            'player2_street_total':37,
            'player2_status':38,
            'player3_position':39,
            'player3_stacksize':40,
            'player3_street_total':41,
            'player3_status':42,
            'ordinal': [0,20,21,22,23,26,27,30,31,34],
            'continuous': [1,23,25,26,28,29,32,33],
            'hand_board':[2,3,4,5,6,7,8,9] + [10,11,12,13,14,15,16,17,18,19]
        }
        self.obs_mapping = {
            'hero_position':0,
            'hero_stacksize':1,
            'hero_hand':[2,3,4,5,6,7,8,9],
            'hero_ranks':[2,4,6,8],
            'hero_suits':[3,5,7,9],
            'villain_position':10,
            'villain_stacksize':11,
            'villain_hand':[12,13,14,15,16,17,18,19],
            'villain_ranks':[12,14,16,18],
            'villain_suits':[13,15,17,19],
            'board':[20,21,22,23,24,25,26,27,28,29],
            'board_ranks':[20,22,24,26,28],
            'board_suits':[21,23,25,27,29],
            'street':30,
            'last_aggressive_position':31,
            'last_aggressive_action':32,
            'last_aggressive_betsize':33,
            'last_position':34,
            'last_action':35,
            'last_betsize':36,
            'blind':37,
            'pot':38,
            'amount_to_call':39,
            'pot_odds':40,
            'player1_position':41,
            'player1_stacksize':42,
            'player1_street_total':43,
            'player1_status':44,
            'player2_position':45,
            'player2_stacksize':46,
            'player2_street_total':47,
            'player2_status':48,
            'ordinal': [0,10,30,31,32,34,37,40,41,44],
            'continuous': [1,23,25,26,28,29,31,32,35,36,38,39,42,43],
            'hand_board':[2,3,4,5,6,7,8,9] + [20,21,22,23,24,25,26,27,28,29],
            'villain_board':[12,13,14,15,16,17,18,19] + [20,21,22,23,24,25,26,27,28,29],
            'hands_and_board':[2,3,4,5,6,7,8,9] + [12,13,14,15,16,17,18,19] + [20,21,22,23,24,25,26,27,28,29],
        }