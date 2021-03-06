import torch
import pickle
import copy

from data_classes import Rules,Evaluator,Pot,GameTurn,Deck,Players,History
import datatypes as pdt

class Poker(object):
    def __init__(self,params):
        self.params = params
        self.game = params['game']
        self.street = 3
        print(f'Initializating poker game {self.game}')
        self.state_params = params['state_params']
        self.ranks = params['state_params']['ranks']
        self.suits = params['state_params']['suits']
        self.evaluator = Evaluator(self.game)
        self.rules = Rules(self.params['rule_params'])
        self.maxlen = 10
        # State attributes
        self.stacksize = self.state_params['stacksize']
        self.n_players = self.state_params['n_players']
        self.pot = Pot(self.state_params['pot'])
        self.game_turn = GameTurn(self.state_params['game_turn'])
        self.stacksizes = torch.Tensor(self.n_players).fill_(self.stacksize)
        self.deck = Deck(self.state_params['ranks'],self.state_params['suits'])
        self.deck.shuffle()
        cards = self.deck.deal(self.state_params['cards_per_player'] * self.n_players)
        hands = [cards[player * self.state_params['cards_per_player']:(player+1) * self.state_params['cards_per_player']] for player in range(self.n_players)]
        self.players = Players(self.n_players,self.stacksizes,hands)
        if self.suits != None:
            self.board = self.deck.deal(5)
        self.history = History()
        self.initialize_functions()

    def initialize_functions(self):
        func_dict = {
            pdt.GameTypes.KUHN : {'return_state':self.return_kuhn_state},
            pdt.GameTypes.COMPLEXKUHN : {'return_state':self.return_kuhn_state},
            pdt.GameTypes.BETSIZEKUHN : {'return_state':self.return_kuhn_state},
            pdt.GameTypes.HISTORICALKUHN : {'return_state':self.return_historical_kuhn_state}
        }
        betsize_funcs = {
            pdt.LimitTypes.LIMIT : self.return_limit_betsize,
            pdt.LimitTypes.NO_LIMIT : self.return_nolimit_betsize,
            pdt.LimitTypes.POT_LIMIT : self.return_potlimit_betsize,
        }
        self.return_state = func_dict[self.game]['return_state']
        self.return_betsize = betsize_funcs[self.rules.bettype]
        # Records action frequencies per street
        self.action_records = {
            0:{i:0 for i in range(5)},
            1:{i:0 for i in range(5)},
            2:{i:0 for i in range(5)},
            3:{i:0 for i in range(5)}
        }
        self.nO = self.return_state()[1].size()[-1]
        self.nS = self.return_state()[0].size()[-1]

    def save_state(self,path=None):
        path = self.params['save_path'] if path is None else path
        with open(path, 'wb') as handle:
            pickle.dump(self.params, handle, protocol = pickle.HIGHEST_PROTOCOL)  
    
    def load_env(self,path=None):
        path = self.params['save_path'] if path is None else path
        with open(path, 'rb') as handle:
            b = pickle.load(handle)
        return b
        
    def load_scenario(self,scenario:dict):
        '''
        Game state consists of [Players,Pot,History,Deck]
        '''
        self.history = copy.deepcopy(scenario['history'])
        self.pot = copy.deepcopy(scenario['pot'])
        self.deck = copy.deepcopy(scenario['deck'])
        self.players = copy.deepcopy(scenario['players'])
        self.game_turn = copy.deepcopy(scenario['game_turn'])
        
    def save_scenario(self):
        scenario = {
            'history':copy.deepcopy(self.history),
            'pot':copy.deepcopy(self.pot),
            'deck':copy.deepcopy(self.deck),
            'players':copy.deepcopy(self.players),
            'game_turn':copy.deepcopy(self.game_turn),
        }
        return scenario
        
    def reset(self):
        """
        resets env state to initial state (can be preloaded).
        """
        self.action_records = {
            0:{i:0 for i in range(5)},
            1:{i:0 for i in range(5)},
            2:{i:0 for i in range(5)},
            3:{i:0 for i in range(5)}
        }
        self.history.reset()
        self.pot.reset()
        self.game_turn.reset()
        self.deck.reset()
        self.deck.shuffle()
        cards = self.deck.deal(self.state_params['cards_per_player'] * self.n_players)
        hands = [cards[player * self.state_params['cards_per_player']:(player+1) * self.state_params['cards_per_player']] for player in range(self.n_players)]
        self.players.reset(hands)
        self.history.add(self.players.current_player,5,0)
        state,obs = self.return_state()
        player_state,player_obs = self.return_player_states(state,obs)
        if self.game == pdt.GameTypes.HISTORICALKUHN:
            self.players.store_history(player_state)
        self.players.store_states(state,obs)
        if self.suits != None:
            self.board = self.deck.deal(5)
        action_mask,betsize_mask = self.action_mask(state)
        self.players.store_masks(action_mask,betsize_mask)
        return state,player_state,obs,self.game_over,action_mask,betsize_mask

    def record_action(self,action):
        self.action_records[self.street][action] += 1
    
    def increment_turn(self):
        self.players.increment()
        self.game_turn.increment()

    def step(self,actor_outputs):
        if self.rules.betsize == True:
            if self.rules.network_output == 'flat':
                if 'value' in actor_outputs:
                    self.players.store_values(actor_outputs)
                flat_outputs = {
                    'action':actor_outputs['action_category'],
                    'action_prob':actor_outputs['action_prob'],
                    'action_probs':actor_outputs['action_probs'],
                    'betsize':actor_outputs['betsize']
                    }
                self.players.store_actor_outputs(flat_outputs)
                self.update_state(actor_outputs['action_category'],actor_outputs['betsize'])
                state,obs = self.return_state(actor_outputs['action_category'])
            else:
                self.players.store_actor_outputs(actor_outputs)
                self.update_state(actor_outputs['action'],actor_outputs['betsize'])
                state,obs = self.return_state(actor_outputs['action'])
        else:
            self.players.store_actor_outputs(actor_outputs)
            self.update_state(actor_outputs['action'])
            state,obs = self.return_state(actor_outputs['action'])
        action_mask,betsize_mask = self.action_mask(state)
        player_state,player_obs = self.return_player_states(state,obs)
        done = self.game_over
        if done == False:
            if self.game == pdt.GameTypes.HISTORICALKUHN:
                self.players.store_history(player_state)
            if state.size(0) > 1:
                self.players.store_states(state[-1,:].unsqueeze(0),obs[-1,:].unsqueeze(0))
            else:
                self.players.store_states(state,obs)
            self.players.store_masks(action_mask,betsize_mask)
        else:
            self.determine_winner()
        return state,player_state,obs,done,action_mask,betsize_mask
    
    def update_state(self,action,betsize_category=None):
        """Updates the current environment state by processing the current action."""
        action_int = action.item()
        self.record_action(action_int)
        bet_amount = self.return_betsize(action_int,betsize_category)
        self.history.add(self.players.current_player,action_int,bet_amount)
        self.pot.add(bet_amount)
        self.players.update_stack(-bet_amount)
        self.increment_turn()
        
    def ml_inputs(self,serialize=False):
        raw_ml = self.players.get_inputs()
        positions = raw_ml.keys()
        # convert to torch
        for position in positions:
            if len(raw_ml[position]['game_states']):
                assert(isinstance(raw_ml[position]['game_states'][0],torch.Tensor))
                assert(isinstance(raw_ml[position]['observations'][0],torch.Tensor))
                assert(isinstance(raw_ml[position]['actions'][0],torch.Tensor))
                assert(isinstance(raw_ml[position]['action_prob'][0],torch.Tensor))
                assert(isinstance(raw_ml[position]['action_probs'][0],torch.Tensor))
                assert(isinstance(raw_ml[position]['rewards'][0],torch.Tensor))
                # assert(isinstance(raw_ml[position]['values'][0],torch.Tensor))
                if self.game == pdt.GameTypes.HISTORICALKUHN:
                    raw_ml[position]['historical_game_states'] = torch.stack(raw_ml[position]['historical_game_states']).view(-1,self.maxlen,self.state_space)
                raw_ml[position]['game_states'] = torch.stack(raw_ml[position]['game_states']).view(-1,self.state_space)
                raw_ml[position]['observations'] = torch.stack(raw_ml[position]['observations']).view(-1,self.observation_space)
                raw_ml[position]['actions'] = torch.stack(raw_ml[position]['actions']).view(-1,1)
                raw_ml[position]['action_prob'] = torch.stack(raw_ml[position]['action_prob']).view(-1,1)
                raw_ml[position]['rewards'] = torch.stack(raw_ml[position]['rewards']).view(-1,1)
                raw_ml[position]['action_masks'] = torch.stack(raw_ml[position]['action_masks']).view(-1,self.action_space)
                raw_ml[position]['betsize_masks'] = torch.stack(raw_ml[position]['betsize_masks']).view(-1,self.betsize_space)
                # raw_ml[position]['full_states'] = torch.cat((hand,combined_states),dim=-1).view(-1,self.state_space)
                if self.rules.betsize == True:
                    if self.rules.network_output == 'flat':
                        raw_ml[position]['betsizes'] = torch.stack(raw_ml[position]['betsizes']).view(-1,1)
                        raw_ml[position]['action_probs'] = torch.stack(raw_ml[position]['action_probs']).view(-1,self.action_space - 2 + self.betsize_space)
                    else:
                        raw_ml[position]['betsizes'] = torch.stack(raw_ml[position]['betsizes']).view(-1,1)
                        raw_ml[position]['betsize_prob'] = torch.stack(raw_ml[position]['betsize_prob']).view(-1,1)
                        raw_ml[position]['betsize_probs'] = torch.stack(raw_ml[position]['betsize_probs']).view(-1,self.betsize_space)
                        raw_ml[position]['action_probs'] = torch.stack(raw_ml[position]['action_probs']).view(-1,self.action_space)
                else:
                    raw_ml[position]['action_probs'] = torch.stack(raw_ml[position]['action_probs']).view(-1,self.action_space)
                # raw_ml[position]['values'] = torch.stack(raw_ml[position]['values']).view(-1,1)
                if serialize == True:
                    raw_ml[position]['action_probs'] = raw_ml[position]['action_probs'].detach()
                    raw_ml[position]['action_prob'] = raw_ml[position]['action_prob'].detach()

        return raw_ml
        
    @property
    def db_mapping(self):
        """
        Required for inserting the data into mongodb properly
        """
        return self.rules.db_mapping

    @property
    def game_over(self):
        return self.rules.over(self)
    
    @property
    def state_space(self):
        return self.nS
    
    @property
    def observation_space(self):
        return self.nO
    
    @property
    def action_space(self):
        return self.rules.action_space

    @property
    def betsize_space(self):
        return self.rules.num_betsizes

    @property
    def current_player(self):
        return self.players.current_player

    def determine_holdem(self):
        if self.history.last_action == pdt.Globals.REVERSE_ACTION_ORDER[pdt.Actions.FOLD]:
            self.players.update_stack(self.pot.value)
        else:
            hands = self.players.get_hands()
            hand1,hand2 = hands
            winner_idx = self.evaluator([hand1,hand2,self.board])
            winner_position = self.players.initial_positions[winner_idx]
            self.players.update_stack(self.pot.value,winner_position)
        self.players.gen_rewards()

    def determine_winner(self):
        """
        Two cases, showdown and none showdown. There are no ties in Kuhn.
        """
        if self.history.last_action == pdt.Globals.REVERSE_ACTION_ORDER[pdt.Actions.FOLD]:
            self.players.update_stack(self.pot.value)
        else:
            hands = self.players.get_hands()
            winner_idx = self.evaluator(hands)
            winner_position = self.players.initial_positions[winner_idx]
            self.players.update_stack(self.pot.value,winner_position)
        self.players.gen_rewards()

    def return_holdem_state(self,action=None):
        """
        Current player's hand. Previous action
        """
        current_hand = torch.tensor([[card.rank,card.suit] for card in self.players.current_hand]).view(-1).squeeze(0)
        vil_hand = torch.tensor([[card.rank,card.suit] for card in self.players.previous_hand]).view(-1).squeeze(0)
        board = torch.tensor([[card.rank,card.suit] for card in self.board]).view(-1).squeeze(0)
        if not isinstance(action,torch.Tensor):
            action = torch.Tensor([self.rules.unopened_action])
        state = torch.cat((current_hand.float(),board.float(),action.float())).unsqueeze(0)
        # Obs
        obs = torch.cat((current_hand.float(),vil_hand.float(),board.float(),action.float())).unsqueeze(0)
        return state,obs

    def encode_history(self):
        points = []
        for i in range(len(self.history)): #pdt.Globals.POSITION_MAPPING[self.history[i].player],
            points.append(torch.tensor([self.history[i].action.item(),self.history[i].betsize]).unsqueeze(0).float())
        return points

    def return_player_states(self,state,obs):
        B = len(self.history)
        n_padding = self.maxlen - B
        assert (n_padding > 0)
        padding = torch.zeros(n_padding,self.state_space)
        obs_padding = torch.zeros(n_padding,self.observation_space)
        player_state = torch.cat((state,padding),dim=0)
        player_obs = torch.cat((obs,obs_padding),dim=0)
        return player_state,player_obs

    def return_historical_kuhn_state(self,action=None):
        """
        Current player's hand. Previous action, Previous betsize (Not always used by network)
        """
        points = self.encode_history()
        if len(points) > 0:
            B = len(self.history)
            hist_points = torch.stack(points).squeeze(1)
            current_hands = torch.tensor([card.rank for card in self.players.current_hand]).repeat(B,1).float()
            vil_hands = torch.tensor([card.rank for card in self.players.previous_hand]).repeat(B,1).float()
            state = torch.cat([current_hands,hist_points],dim=-1)
            obs = torch.cat([current_hands,vil_hands,hist_points],dim=-1)
        else:
            state,obs = self.return_kuhn_state(action)
            n_padding = self.maxlen - 1
        return state,obs
        
    def return_kuhn_state(self,action=None):
        """
        Current player's hand. Previous action, Previous betsize (Not always used by network)
        """
        current_hand = torch.tensor([card.rank for card in self.players.current_hand])
        vil_hand = torch.tensor([card.rank for card in self.players.previous_hand])
        if not isinstance(action,torch.Tensor):
            action = torch.Tensor([self.rules.unopened_action])
            previous_betsize = torch.tensor([0.])
        else:
            previous_betsize = self.history.last_betsize
        state = torch.cat((current_hand.float(),action.float(),previous_betsize.float())).unsqueeze(0)
        # Obs
        obs = torch.cat((current_hand.float(),vil_hand.float(),action.float(),previous_betsize.float())).unsqueeze(0)
        return state,obs

    def action_mask(self,state):
        """
        Called from outside when training.
        Grabs last action, return mask of action possibilities. Requires categorical action selection.
        Knows which actions represent bets and their size. When it is a bet, checks stack sizes to make sure betting/calling
        etc. are valid. If both players are allin, then game finishes.
        """
        available_categories = self.rules.return_mask(state)
        available_betsizes = self.return_betsizes(state)
        # if available_categories[pdt.Globals.REVERSE_ACTION_ORDER['raise']] == 1 or available_categories[pdt.Globals.REVERSE_ACTION_ORDER['bet']] == 1:
        if available_betsizes.sum() == 0:
            if self.action_space == 5:
                available_categories[pdt.Globals.REVERSE_ACTION_ORDER[pdt.Actions.RAISE]] = 0
        return available_categories,available_betsizes

    def return_betsizes(self,state):
        """Returns possible betsizes. If betsize > player stack no betsize is possible"""
        possible_betsizes = torch.zeros((self.rules.num_betsizes))
        if self.history.last_betsize > 0:
            if self.history.last_action == pdt.Globals.REVERSE_ACTION_ORDER[pdt.Actions.RAISE]:
                previous_betsize = self.history.last_betsize - self.history.penultimate_betsize
            else:
                previous_betsize = self.history.last_betsize
            if previous_betsize < self.players.current_stack:
                # player allin is always possible if stack > betsize.
                for i,betsize in enumerate(self.rules.betsizes,0):
                    possible_betsizes[i] = 1
                    if betsize * self.pot.value >= self.players.current_stack:
                        break
        elif state[-1,self.rules.db_mapping['state']['previous_action']] == 5 or state[-1,self.rules.db_mapping['state']['previous_action']] == 0:
            for i,betsize in enumerate(self.rules.betsizes,0):
                possible_betsizes[i] = 1
                if betsize * self.pot.value >= self.players.current_stack:
                    break
        return possible_betsizes

    ## LIMIT ##
    def return_limit_betsize(self,action,betsize_category):
        """TODO Betsizes should be indexed by street"""
        if action == pdt.Globals.REVERSE_ACTION_ORDER[pdt.Actions.CALL]: # Call
            betsize = min(1,self.players.current_stack)
        elif action == pdt.Globals.REVERSE_ACTION_ORDER[pdt.Actions.BET]: # Bet
            betsize = min(1,self.players.current_stack)
        elif action == pdt.Globals.REVERSE_ACTION_ORDER[pdt.Actions.RAISE]: # Raise
            betsize = min(2,self.players.current_stack)
        else: # fold or check
            betsize = 0
        return torch.tensor([betsize])

    ## NO LIMIT ##
    def return_nolimit_betsize(self,action,betsize_category):
        """Betsize_category in NL is a float [0,1] representing percentage of pot"""
        if action > 1:
            if action == pdt.Globals.REVERSE_ACTION_ORDER[pdt.Actions.CALL]:
                betsize = min(self.history.last_betsize - self.history.penultimate_betsize,self.players.current_stack)
            elif action == pdt.Globals.REVERSE_ACTION_ORDER[pdt.Actions.BET]: # Bet
                betsize_value = self.rules.betsizes[betsize_category.long()] * self.pot.value
                betsize = min(max(self.rules.minbet,betsize_value),self.players.current_stack)
            elif action == pdt.Globals.REVERSE_ACTION_ORDER[pdt.Actions.RAISE]: # Raise
                betsize_value = self.rules.betsizes[betsize_category.long()] * self.pot.value
                betsize = min(max(self.history.last_betsize * 2,betsize_value),self.players.current_stack)
        else:
            betsize = 0
        return torch.tensor([betsize])
            
    ## POT LIMIT
    def return_potlimit_betsize(self,action,betsize_category):
        """TODO Betsize_category in POTLIMIT is a float [0,1] representing fraction of pot"""
        if action > 2:
            min_betsize = self.rules.minbet if action == 3 else self.history.last_betsize * 2
            betsize = min(max(min_betsize,self.rules.betsizes[betsize_category.long()] * self.pot.value),self.players.current_stack)
        else:
            betsize = 0
        return torch.tensor([betsize])
        