from train import train
from poker.config import Config
from poker_env import Poker
from agents.agent import Agent,Priority_DQN,return_agent
from db import MongoDB
import poker.datatypes as pdt
from models.network_config import NetworkConfig,CriticType

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=
        """
        Run RL experiments with varying levels of complexity in poker.\n\n
        Modify the traiing params via the config file.\n
        """)

    parser.add_argument('--agent',
                        default='actor_critic',
                        metavar="['actor','actor_critic']",
                        type=str,
                        help='Which agent to train')
    parser.add_argument('--env',
                        default=pdt.GameTypes.KUHN,
                        type=str,
                        metavar=f"[{pdt.GameTypes.KUHN},{pdt.GameTypes.COMPLEXKUHN},{pdt.GameTypes.HOLDEM}]",
                        help='Picks which type of poker env to train in')
    parser.add_argument('--clean',
                        default=True,
                        type=bool,
                        help='cleans database')
    parser.add_argument('--store',
                        default=True,
                        type=bool,
                        help='Stores training data in database')
    parser.add_argument('-e','--epochs',
                        default=1000,
                        type=int,
                        help='Number of training epochs')
    parser.add_argument('--critic',
                        default='q',
                        type=str,
                        metavar="['q','reg']",
                        help='Critic output types [nA,1]')

    args = parser.parse_args()

    print(f'args {args}')
    
    game_object = pdt.Globals.GameTypeDict[args.env]
    config = Config()
    config.agent = args.agent
    params = {'game':args.env}
    params['state_params'] = game_object.state_params
    params['rule_params'] = game_object.rule_params
    agent_params = config.agent_params

    env_networks = NetworkConfig.EnvModels[args.env]
    agent_params['network'] = env_networks['actor']
    agent_params['actor_network'] = env_networks['actor']
    agent_params['critic_network'] = env_networks['critic'][args.critic]
    print(agent_params['critic_network'],env_networks['critic'])
    agent_params['mapping'] = params['rule_params']['mapping']
    agent_params['max_reward'] = params['state_params']['stacksize'] + params['state_params']['pot']
    agent_params['epochs'] = int(args.epochs)

    training_data = {}
    for position in pdt.Globals.PLAYERS_POSITIONS_DICT[params['state_params']['n_players']]:
        training_data[position] = []
        
    training_params = config.training_params
    training_params['epochs'] = int(args.epochs)
    training_params['training_data'] = training_data
    training_params['agent_name'] = f'{args.env}_baseline'
    training_params['agent_type'] = args.agent

    env = Poker(params)

    nS = env.state_space
    nO = env.observation_space
    nA = env.action_space
    print(f'Environment: State Space {nS}, Obs Space {nO}, Action Space {nA}')
    seed = 154

    agent = return_agent(args.agent,nS,nO,nA,seed,agent_params)
    action_data = train(env,agent,training_params)

    if args.store == True:
        mongo = MongoDB()
        if args.clean:
            print('Cleaning db')
            mongo.clean_db()
        mongo.store_data(action_data,env.db_mapping,training_params['training_round'],env.game)